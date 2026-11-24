import re

from .text import numbers, sentences, tokens

ABSTAIN_PHRASES = ["can't find", "cannot find", "can not find", "not in the documents", "do not contain", "don't contain",
                   "does not contain", "doesn't contain", "no information", "not mentioned", "not specified", "not covered",
                   "don't have information", "do not have information", "not provided"]


def strip_answer(text):
    text = re.sub(r"<quotes>.*?</quotes>", "", text, flags=re.S)
    text = re.sub(r"Sources:\s*\[[^\]]*\]", "", text)
    return text.strip()


def is_abstain(text):
    t = text.lower().replace("’", "'")
    return any(p in t for p in ABSTAIN_PHRASES)


def _has(alt, norm):
    alt = alt.lower().replace(",", "")
    if re.fullmatch(r"[\d.]+", alt):
        return re.search(rf"(?<![\d.]){re.escape(alt)}(?![\d])", norm) is not None
    return alt in norm


def grade(task, result):
    answer = strip_answer(result["answer"])
    norm = answer.lower().replace(",", "").replace("’", "'")
    abstained = is_abstain(answer)
    if task.get("expect_abstain"):
        correct = abstained
    else:
        correct = (not abstained) and all(any(_has(a, norm) for a in group) for group in task["facts"])
    return {"correct": bool(correct), "grounded": groundedness(answer, result["context"], abstained), "abstained": abstained}


def groundedness(answer, context, abstained):
    """Share of answer sentences whose numbers all appear in the retrieved context and whose words mostly do."""
    if abstained:
        return 1.0
    sents = sentences(answer)
    if not sents:
        return 0.0
    ctx_tokens, ctx_nums = set(tokens(context)), numbers(context)
    ok = 0
    for s in sents:
        toks = tokens(s)
        overlap = sum(t in ctx_tokens for t in toks) / max(1, len(toks))
        if numbers(s) <= ctx_nums and overlap >= 0.5:
            ok += 1
    return ok / len(sents)
