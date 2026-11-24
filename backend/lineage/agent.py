"""The reference agent: an enterprise policy and support assistant over a fixed document set."""
import re

from .providers import ABSTAIN_TEXT, REWRITE_MARKER, VERIFY_MARKER
from .retrieval import get_index

FEW_SHOT = [
    ("Who approves an expense report over $5,000?", "travel-expense-policy",
     "The employee's manager and a Vice President must approve it."),
    ("Are branch staff allowed to work remotely?", "remote-work-policy", "No. Branch staff are not eligible for remote work."),
    ("What happens to a wire received after the cutoff?", "wire-transfer-procedures", "It is processed the next business day."),
]


def build_system(config):
    p = config["prompt"]
    parts = [p["system"]]
    if p["quote_first"]:
        parts.append("First extract the exact quotes from the documents that are relevant to the question inside <quotes></quotes> tags. "
                     "Then answer using only those quotes.")
    if p["abstain_when_unsure"]:
        parts.append(f"If the documents do not contain the answer, reply exactly: {ABSTAIN_TEXT}")
    if p["cite_sources"]:
        parts.append("End your answer with a line in the form Sources: [doc-id, ...] listing the ids of the documents you used.")
    parts.append("Be concise.")
    return "\n".join(parts)


def build_user(config, chunks, question):
    docs = "\n".join(f'<document id="{c.doc_id}" title="{c.title}">{c.index_text}</document>' for c in chunks)
    shots = ""
    n = config["prompt"]["few_shot"]
    if n:
        shots = "Examples:\n" + "\n".join(f"Q: {q}\nA: {a}" for q, _, a in FEW_SHOT[:n]) + "\n\n"
    return f"<documents>\n{docs}\n</documents>\n\n{shots}Question: {question}"


def parse_sources(text):
    m = re.search(r"Sources:\s*\[([^\]]*)\]", text)
    return [s.strip() for s in m.group(1).split(",") if s.strip()] if m else []


def run(config, question, model, seed_key=""):
    mp = config["model_params"]
    r = config["retrieval"]
    calls = []
    query = question
    if r["query_rewrite"]:
        c = model.complete(f"{REWRITE_MARKER}. Return only the query.", f"Question: {question}", 0.0, 100, seed_key)
        calls.append(c)
        query = c.text.strip() or question
    chunks = get_index(r["chunk_size"], r["contextual_chunks"]).search(query, r["top_k"])
    system = build_system(config)
    user = build_user(config, chunks, question)
    c = model.complete(system, user, mp["temperature"], mp["max_tokens"], seed_key)
    calls.append(c)
    text = c.text
    if config["reasoning"]["self_check"]:
        verify_user = (f"<instructions>{system}</instructions>\n{user}\n\n<draft>{text}</draft>\n\n"
                       "Return the corrected final answer in the same format, or the draft unchanged if it is correct.")
        c = model.complete(f"{VERIFY_MARKER}. Fix any claim the documents do not support.", verify_user,
                           0.0, mp["max_tokens"], seed_key)
        calls.append(c)
        text = c.text
    return {
        "answer": text,
        "citations": parse_sources(text),
        "retrieved": [c.doc_id for c in chunks],
        "context": " ".join(c.index_text for c in chunks),
        "calls": len(calls),
        "input_tokens": sum(c.input_tokens for c in calls),
        "output_tokens": sum(c.output_tokens for c in calls),
        "cost_usd": sum(c.cost_usd for c in calls),
        "latency_ms": sum(c.latency_ms for c in calls),
    }
