"""The reference agent's behavior surface. Every technique the Replicator can test is a patch to this config."""
import copy

DEFAULT_CONFIG = {
    "prompt": {
        "system": "You are an assistant for Meridian Federal Bank employees. Answer the question using the documents provided.",
        "quote_first": False,
        "cite_sources": False,
        "abstain_when_unsure": False,
        "few_shot": 0,
    },
    "retrieval": {"top_k": 3, "chunk_size": 120, "contextual_chunks": False, "query_rewrite": False},
    "reasoning": {"self_check": False},
    "model_params": {"temperature": 0.0, "max_tokens": 600},
}

KNOBS = {
    "prompt.system": (str, "The system prompt text."),
    "prompt.quote_first": (bool, "Extract relevant quotes from the documents before answering (long-context quote extraction)."),
    "prompt.cite_sources": (bool, "Require the answer to end with the document ids it used."),
    "prompt.abstain_when_unsure": (bool, "Tell the model to say it can't find the answer when the documents don't contain it."),
    "prompt.few_shot": (int, "Number of worked examples (0-3) included in the prompt."),
    "retrieval.top_k": (int, "Number of chunks retrieved (1-10)."),
    "retrieval.chunk_size": (int, "Chunk size in words (40-400)."),
    "retrieval.contextual_chunks": (bool, "Prepend document title and section context to every chunk before indexing (contextual retrieval)."),
    "retrieval.query_rewrite": (bool, "Have the model rewrite the question into a search query before retrieval."),
    "reasoning.self_check": (bool, "A second model call verifies the draft answer against the documents and fixes it."),
    "model_params.temperature": (float, "Sampling temperature (0-1)."),
    "model_params.max_tokens": (int, "Max output tokens (100-2000)."),
}

RANGES = {
    "prompt.few_shot": (0, 3),
    "retrieval.top_k": (1, 10),
    "retrieval.chunk_size": (40, 400),
    "model_params.temperature": (0.0, 1.0),
    "model_params.max_tokens": (100, 2000),
}


def flatten(config, prefix=""):
    out = {}
    for k, v in config.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def validate_patch(patch):
    """Return (clean_patch, errors). Patch is a flat {"section.knob": value} dict."""
    clean, errors = {}, []
    for key, value in (patch or {}).items():
        if key not in KNOBS:
            errors.append(f"unknown knob {key}")
            continue
        typ = KNOBS[key][0]
        try:
            value = typ(value) if typ is not bool else (value if isinstance(value, bool) else str(value).lower() == "true")
        except (TypeError, ValueError):
            errors.append(f"bad value for {key}: {value!r}")
            continue
        if key in RANGES:
            lo, hi = RANGES[key]
            value = max(lo, min(hi, value))
        clean[key] = value
    return clean, errors


def apply_patch(config, patch):
    new = copy.deepcopy(config)
    for key, value in patch.items():
        section, knob = key.split(".", 1)
        new.setdefault(section, {})[knob] = value
    return new


def config_diff(old, new):
    a, b = flatten(old), flatten(new)
    return [{"path": k, "from": a.get(k), "to": b.get(k)} for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
