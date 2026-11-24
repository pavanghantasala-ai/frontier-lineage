"""Extractor: turns a scouted item into a claim card with a pre-registered test."""
import json
import re

from . import db
from .config import KNOBS, validate_patch
from .providers import available_models

DEFAULT_TEST = {"primary_metric": "accuracy", "min_delta": 0.03, "max_groundedness_drop": 0.03, "max_cost_increase": 1.0}

PROMPT = """You read posts from AI labs and decide whether they describe a technique that can be tested on a
retrieval-augmented policy Q&A agent. The agent's behavior is controlled ONLY by these knobs:
{knobs}

Return a single JSON object, no prose:
{{"is_technique": bool,            // false for product launches, funding, policy, hiring news
 "title": str, "claim": str,       // the post's claim in one sentence, stated fairly
 "mechanism": str,                 // how the technique works
 "test_plan": str,                 // how we test it on the agent
 "requirements": str,              // model features it needs
 "effort": "low"|"medium"|"high",
 "expected_impact": 1-5,
 "testable": bool,                 // true only if expressible with the knobs above
 "config_patch": {{"knob.name": value}},   // ONE technique, minimal change
 "untestable_reason": str,
 "source_quotes": [str]}}           // up to 3 sentences copied VERBATIM from the post that support the claim

Post title: {title}
Post URL: {url}
Post text:
{text}"""

RULES = [
    (r"contextual retrieval|chunk-specific (explanatory )?context", {"retrieval.contextual_chunks": True},
     "Adding document context to each chunk before indexing reduces retrieval failures."),
    (r"extract (the )?(relevant )?quotes|quotes relevant to the question", {"prompt.quote_first": True},
     "Extracting relevant quotes before answering improves long-document answers."),
    (r"evaluator-optimizer|evaluates it and provides feedback|self-verif|self-check", {"reasoning.self_check": True},
     "A second call that evaluates and corrects the draft improves answers."),
    (r"lacks the information|say that it does not know|i don't know", {"prompt.abstain_when_unsure": True},
     "Telling the model what to do when the context lacks the answer reduces guessing."),
    (r"smallest set of high-signal tokens", {"retrieval.top_k": 2},
     "Less but higher-signal context gives better results than filling the window."),
    (r"multishot prompting|few-shot", {"prompt.few_shot": 3},
     "A few worked examples in the prompt improve accuracy and consistency."),
    (r"query rewrit|rewrite the query", {"retrieval.query_rewrite": True},
     "Rewriting the user's question before retrieval improves recall."),
]


def _sentences_with(text, pattern, n=2):
    sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if re.search(pattern, s, re.I)][:n]


def extract_rules(item):
    for pattern, patch, claim in RULES:
        if re.search(pattern, item["text"], re.I):
            return {"is_technique": True, "title": item["title"], "claim": claim,
                    "mechanism": f"Change: {', '.join(f'{k} = {v}' for k, v in patch.items())}",
                    "test_plan": "Apply the change to the current reference agent and compare against it on the graded suite.",
                    "requirements": "Any chat model", "effort": "low", "expected_impact": 3, "testable": True,
                    "config_patch": patch, "untestable_reason": "", "source_quotes": _sentences_with(item["text"], pattern),
                    "extractor": "rules"}
    return {"is_technique": False, "title": item["title"], "extractor": "rules"}


def extract_llm(item, model):
    knobs = "\n".join(f"- {k} ({t.__name__}): {d}" for k, (t, d) in KNOBS.items())
    prompt = PROMPT.format(knobs=knobs, title=item["title"], url=item["url"], text=item["text"][:10000])
    c = model.complete("You are a careful research engineer. Output JSON only.", prompt, 0.0, 1200)
    m = re.search(r"\{.*\}", c.text, re.S)
    card = json.loads(m.group(0))
    card["extractor"] = model.id
    return card, c.cost_usd


def fidelity(card, text):
    """Share of the card's source quotes that appear verbatim in the post."""
    quotes = card.get("source_quotes") or []
    if not quotes:
        return 0.0
    norm = " ".join(text.split()).lower()
    return sum(" ".join(q.split()).lower().rstrip(".") in norm for q in quotes) / len(quotes)


def extractor_models():
    return [m for m in available_models() if not m.is_mock]


_disabled = set()


def reset_failures():
    _disabled.clear()


def extract_item(item, log=print):
    card, cost = None, 0.0
    for model in extractor_models():
        if model.id in _disabled:
            continue
        try:
            card, cost = extract_llm(item, model)
            break
        except Exception as e:
            _disabled.add(model.id)
            log(f"extractor: {model.id} failed, skipping it for the rest of this cycle: {str(e)[:160]}")
    if card is None:
        card = extract_rules(item)
    if not card.get("is_technique"):
        db.update("items", item["id"], status="not_technique")
        return None
    patch, errors = validate_patch(card.get("config_patch"))
    card["config_patch"] = patch
    if errors:
        card["patch_errors"] = errors
    if not patch:
        card["testable"] = False
        card["untestable_reason"] = card.get("untestable_reason") or "Needs code or tool changes beyond the config surface."
    for k, v in DEFAULT_TEST.items():
        card.setdefault(k, v)
    card.update({"lab": item["lab"], "url": item["url"], "published": item["published"], "fidelity": fidelity(card, item["text"]),
                 "extract_cost_usd": cost})
    status = "ready" if card.get("testable") and patch else "untestable"
    card_id = db.insert("cards", item_id=item["id"], data=card, status=status, created_at=db.now())
    db.update("items", item["id"], status="carded")
    db.log("card", card_id, f"{status}: {card.get('title')}")
    return card_id
