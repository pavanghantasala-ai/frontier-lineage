"""Version store: every version keeps its parent, the card that caused it, its config diff and its scores."""
from . import db
from .config import DEFAULT_CONFIG, apply_patch, config_diff


def reference():
    v = db.one("SELECT * FROM versions WHERE status='reference'")
    if v is None:
        vid = db.insert("versions", parent_id=None, card_id=None, label="v0", config=DEFAULT_CONFIG, diff=[],
                        status="reference", created_at=db.now(), promoted_at=db.now())
        db.log("version", vid, "created v0 baseline reference")
        v = db.one("SELECT * FROM versions WHERE id=?", (vid,))
    return v


def get(version_id):
    return db.one("SELECT * FROM versions WHERE id=?", (version_id,))


def replicate(card_id):
    """Replicator: implement a card as a candidate version branched from the current reference."""
    card = db.one("SELECT * FROM cards WHERE id=?", (card_id,))
    parent = reference()
    config = apply_patch(parent["config"], card["data"]["config_patch"])
    if config == parent["config"]:
        db.update("cards", card_id, status="already_in_reference")
        return None
    for v in db.q("SELECT id, config, label FROM versions"):
        if v["config"] == config:
            db.update("cards", card_id, status=f"duplicate_of_{v['label']}")
            return None
    n = db.one("SELECT COUNT(*) AS n FROM versions")["n"]
    vid = db.insert("versions", parent_id=parent["id"], card_id=card_id, label=f"v{n}", config=config,
                    diff=config_diff(parent["config"], config), status="candidate", created_at=db.now())
    db.update("cards", card_id, status="replicated")
    db.log("version", vid, f"candidate v{n} from card {card_id}", {"parent": parent["label"]})
    return get(vid)


def tree():
    versions = db.q("SELECT * FROM versions ORDER BY id")
    evals = db.q("SELECT version_id, model_id, metrics, cost_usd FROM evals ORDER BY id")
    cards = {c["id"]: c for c in db.q("SELECT id, data FROM cards")}
    verdicts = {v["version_id"]: v for v in db.q("SELECT * FROM verdicts ORDER BY id")}
    out = []
    for v in versions:
        scores = {}
        for e in evals:
            if e["version_id"] == v["id"]:
                scores[e["model_id"]] = e["metrics"]
        card = cards.get(v["card_id"])
        verdict = verdicts.get(v["id"])
        out.append({**v, "scores": scores, "card_title": card["data"].get("title") if card else None,
                    "lab": card["data"].get("lab") if card else None,
                    "verdict": verdict["verdict"] if verdict else None, "decision": verdict["decision"] if verdict else None})
    return out
