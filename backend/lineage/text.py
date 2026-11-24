import re

STOP = set("""a an the of to in on for and or is are was were be been do does did i my me we our you your it its
this that what which who whom how when where why can could should would will with by at from as about any
per much many after before into than then there their they he she his her them if not no so up out
""".split())

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def stem(tok):
    for suf in ("ing", "ed", "es", "s"):
        if len(tok) > 4 and tok.endswith(suf):
            return tok[: -len(suf)]
    return tok


def tokens(text):
    return [stem(t) for t in re.findall(r"[a-z0-9]+", text.lower().replace(",", "")) if t not in STOP]


def numbers(text):
    return {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(text)}


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 2]
