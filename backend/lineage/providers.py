import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass

import httpx

from .paths import MODELS
from .text import numbers, sentences, tokens

REWRITE_MARKER = "Rewrite the user's question as a keyword search query"
VERIFY_MARKER = "Check the draft answer against the documents"
QUOTE_MARKER = "<quotes>"
CITE_MARKER = "Sources: ["
ABSTAIN_TEXT = "I can't find that in the documents."


class ProviderError(RuntimeError):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float


class Model:
    def __init__(self, spec):
        self.spec = spec
        self.id = spec["id"]
        self.provider = spec["provider"]
        self.model = spec["model"]
        self.price_in = spec.get("price_in", 0.0)
        self.price_out = spec.get("price_out", 0.0)

    @property
    def is_mock(self):
        return self.provider == "mock"

    @property
    def fingerprint(self):
        """Identity of the deployment answering, so cached scores never cross endpoints."""
        return f"{self.provider}:{self.model}:{getattr(self, 'base_url', '')}"

    def cost(self, tin, tout):
        return (tin * self.price_in + tout * self.price_out) / 1_000_000

    def complete(self, system, user, temperature=0.0, max_tokens=600, seed_key=""):
        raise NotImplementedError

    def info(self):
        return {"id": self.id, "provider": self.provider, "model": self.model, "mock": self.is_mock}


def _post(url, headers, body, tries=4, timeout=120):
    for attempt in range(tries):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 529) and attempt < tries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            if r.status_code >= 400:
                raise ProviderError(f"{r.status_code}: {r.text[:300]}")
            return r.json()
        except httpx.TransportError:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


class AnthropicModel(Model):
    def complete(self, system, user, temperature=0.0, max_tokens=600, seed_key=""):
        t0 = time.time()
        data = _post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": os.environ[self.spec["env"]], "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "system": system,
             "messages": [{"role": "user", "content": user}]},
        )
        text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        u = data["usage"]
        return Completion(text, u["input_tokens"], u["output_tokens"], (time.time() - t0) * 1000, self.cost(u["input_tokens"], u["output_tokens"]))


class OpenAIModel(Model):
    def complete(self, system, user, temperature=0.0, max_tokens=600, seed_key=""):
        t0 = time.time()
        data = _post(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {os.environ[self.spec['env']]}"},
            {"model": self.model, "temperature": temperature, "max_completion_tokens": max_tokens,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
        u = data["usage"]
        return Completion(data["choices"][0]["message"]["content"] or "", u["prompt_tokens"], u["completion_tokens"],
                          (time.time() - t0) * 1000, self.cost(u["prompt_tokens"], u["completion_tokens"]))


class OpenAICompatModel(Model):
    """Any OpenAI-compatible chat endpoint: Ollama, vLLM, Groq, Together, OpenRouter."""

    @property
    def base_url(self):
        return os.environ.get(self.spec.get("base_url_env", ""), self.spec["base_url"]).rstrip("/")

    def headers(self):
        key = os.environ.get(self.spec.get("env", ""), "")
        return {"Authorization": f"Bearer {key}"} if key else {}

    def reachable(self):
        if self.spec.get("env"):
            return bool(os.environ.get(self.spec["env"]))
        try:
            r = httpx.get(f"{self.base_url}/models", headers=self.headers(), timeout=1.5)
            return r.status_code == 200 and any(m.get("id") == self.model for m in r.json().get("data", []))
        except Exception:
            return False

    def complete(self, system, user, temperature=0.0, max_tokens=600, seed_key=""):
        t0 = time.time()
        data = _post(
            f"{self.base_url}/chat/completions", self.headers(),
            {"model": self.model, "temperature": temperature, "max_tokens": max_tokens,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=self.spec.get("timeout", 120),
        )
        u = data.get("usage") or {}
        tin, tout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        return Completion(data["choices"][0]["message"]["content"] or "", tin, tout, (time.time() - t0) * 1000,
                          self.cost(tin, tout))


class GeminiModel(Model):
    def complete(self, system, user, temperature=0.0, max_tokens=600, seed_key=""):
        t0 = time.time()
        data = _post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": os.environ[self.spec["env"]]},
            {"systemInstruction": {"parts": [{"text": system}]},
             "contents": [{"role": "user", "parts": [{"text": user}]}],
             "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
        )
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        u = data.get("usageMetadata", {})
        tin, tout = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
        return Completion(text, tin, tout, (time.time() - t0) * 1000, self.cost(tin, tout))


SYNONYMS = {
    "vacation": "pto paid time off", "holiday": "pto holidays", "home": "remote", "wfh": "remote work",
    "baby": "parental leave caregiver", "stolen": "lost stolen device", "charge": "transaction dispute",
    "payee": "beneficiary", "replaced": "refresh", "replace": "refresh", "buy": "purchase", "bonus": "compensation",
}


class MockModel(Model):
    """Deterministic stand-in for an LLM. It answers by extracting sentences from the documents in the prompt,
    so prompt and retrieval changes have real, emergent effects. error_rate simulates hallucinated numbers."""

    THRESH = 0.34

    def _rng(self, seed_key, purpose):
        h = hashlib.sha256(f"{self.id}|{seed_key}|{purpose}".encode()).hexdigest()
        return random.Random(int(h[:12], 16))

    def complete(self, system, user, temperature=0.0, max_tokens=600, seed_key=""):
        if REWRITE_MARKER in system:
            q = user.split("Question:", 1)[-1].strip()
            extra = " ".join(v for k, v in SYNONYMS.items() if k in q.lower())
            text = f"{q} {extra}".strip()
        elif VERIFY_MARKER in system:
            text = self._verify(user, system, seed_key)
        else:
            text = self._answer(system, user, seed_key)
        tin = int(len((system + user).split()) * 1.33)
        tout = int(len(text.split()) * 1.33) + 1
        rng = self._rng(seed_key, "latency")
        latency = (300 + 0.15 * tin + 8 * tout) * (1 + self.spec.get("error_rate", 0.1)) * rng.uniform(0.8, 1.4)
        return Completion(text, tin, tout, latency, self.cost(tin, tout))

    @staticmethod
    def _docs(user):
        return re.findall(r'<document id="([^"]+)"[^>]*>(.*?)</document>', user, re.S)

    def _answer(self, system, user, seed_key, noisy=True):
        docs = self._docs(user)
        question = user.rsplit("Question:", 1)[-1].strip()
        q = set(tokens(question))
        cands = [(doc_id, s) for doc_id, body in docs for s in sentences(body)]
        if not cands or not q:
            return ABSTAIN_TEXT

        def cover(s):
            return q & set(tokens(s))

        best = max(cands, key=lambda c: len(cover(c[1])))
        score = len(cover(best[1])) / len(q)
        if "can't find that in the documents" in system and score < self.THRESH:
            return ABSTAIN_TEXT
        picked = [best]
        quote_first = QUOTE_MARKER in system
        if quote_first:
            covered = set(cover(best[1]))
            for _ in range(2):
                nxt = max(cands, key=lambda c: len(cover(c[1]) - covered))
                if len(cover(nxt[1]) - covered) == 0:
                    break
                picked.append(nxt)
                covered |= cover(nxt[1])
        answer = " ".join(s for _, s in picked)
        if noisy and self._rng(seed_key, "noise").random() < self.spec.get("error_rate", 0.1):
            answer = re.sub(r"\d+", lambda m: str(int(m.group()) + 7), answer)
        text = answer
        if quote_first:
            text = "<quotes>\n" + "\n".join(s for _, s in picked) + "\n</quotes>\n" + answer
        if CITE_MARKER in system:
            ids = sorted({d for d, _ in picked})
            text += "\nSources: [" + ", ".join(ids) + "]"
        return text

    def _verify(self, user, system, seed_key):
        draft = re.search(r"<draft>(.*?)</draft>", user, re.S)
        draft = draft.group(1).strip() if draft else ""
        context = " ".join(body for _, body in self._docs(user))
        answer_part = re.sub(r"<quotes>.*?</quotes>", "", draft, flags=re.S)
        if numbers(answer_part) <= numbers(context):
            return draft
        inner_system = user.split("<instructions>", 1)[-1].split("</instructions>", 1)[0]
        return self._answer(inner_system, user, seed_key, noisy=False)


def load_specs():
    return json.loads(MODELS.read_text())["models"]


def make_model(spec):
    cls = {"anthropic": AnthropicModel, "openai": OpenAIModel, "gemini": GeminiModel, "openai_compat": OpenAICompatModel,
           "mock": MockModel}[spec["provider"]]
    return cls(spec)


def available_models():
    out = []
    for spec in load_specs():
        if spec["provider"] == "mock":
            out.append(make_model(spec))
        elif spec["provider"] == "openai_compat":
            m = make_model(spec)
            if m.reachable():
                out.append(m)
        elif os.environ.get(spec.get("env", "")):
            out.append(make_model(spec))
    return out


def get_models(ids):
    by_id = {m.id: m for m in available_models()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ValueError(f"models not available (missing API key?): {missing}")
    return [by_id[i] for i in ids]


def default_eval_models():
    real = [m for m in available_models() if not m.is_mock]
    return real if real else [m for m in available_models() if m.is_mock]


def healthy(models, log=print):
    """Drop real models whose API call fails (bad key, no credit) so they don't skew verdicts."""
    ok = []
    for m in models:
        if m.is_mock:
            ok.append(m)
            continue
        try:
            m.complete("Reply with OK.", "OK?", 0.0, 50)
            ok.append(m)
        except Exception as e:
            log(f"models: {m.id} unavailable, skipping it: {str(e)[:160]}")
    return ok
