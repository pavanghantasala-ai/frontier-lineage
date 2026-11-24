"""Write a read-only JSON snapshot of the lab for the public static site."""
import json
from pathlib import Path

from . import api, db

PUBLIC_ITEM_FIELDS = ("id", "lab", "title", "url", "published")


def _write(out: Path, name: str, data):
    p = out / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, default=str))


def export(out):
    out = Path(out)
    status = api.status()
    tested = _tested_models()
    status["cycle"] = {"running": False, "log": [], "error": None}
    status["models"] = [m for m in status["models"] if m["id"] in tested]
    status["default_models"] = sorted(tested)
    status["exported_at"] = db.now()
    _write(out, "status", status)
    _write(out, "diff", api.diff())
    _write(out, "scoreboard", _all_verdicts())
    _write(out, "cards", api.cards())
    for c in db.q("SELECT id FROM cards"):
        card = api.card(c["id"])
        card["item"] = {k: card["item"][k] for k in PUBLIC_ITEM_FIELDS} if card["item"] else None
        _write(out, f"cards/{c['id']}", card)
    _write(out, "versions", api.versions())
    _write(out, "items", api.items())
    _write(out, "ledger", api.ledger())
    return out


def _tested_models():
    return {e["model_id"] for e in db.q("SELECT DISTINCT model_id FROM evals")}


def _all_verdicts():
    """Every verdict, newest first; undecided ones are shown as awaiting review."""
    from .frontier_diff import _card_view
    cards = {c["id"]: c["data"] for c in db.q("SELECT id, data FROM cards")}
    return [_card_view(v, cards) | {"decided_at": v["decided_at"], "created_at": v["created_at"]}
            for v in db.q("SELECT * FROM verdicts ORDER BY id DESC")]
