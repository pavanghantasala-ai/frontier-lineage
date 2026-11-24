"""The human gate. Agents draft, implement and evaluate; only a person publishes verdicts and promotes versions."""
from . import db, lineage_store


def decide(verdict_id, action, note=""):
    v = db.one("SELECT * FROM verdicts WHERE id=?", (verdict_id,))
    if v is None:
        raise ValueError("verdict not found")
    if action == "promote":
        old = lineage_store.reference()
        db.update("versions", v["version_id"], status="reference", promoted_at=db.now())
        db.update("versions", old["id"], status="retired")
        db.update("verdicts", verdict_id, published=1, decision="promoted", decided_at=db.now())
    elif action == "publish":
        db.update("versions", v["version_id"], status="archived")
        db.update("verdicts", verdict_id, published=1, decision="published", decided_at=db.now())
    elif action == "discard":
        db.update("versions", v["version_id"], status="discarded")
        db.update("verdicts", verdict_id, published=0, decision="discarded", decided_at=db.now())
    else:
        raise ValueError(f"unknown action {action}")
    db.log("decision", verdict_id, f"{action}: {note}".strip(": "))


def rollback(version_id, note=""):
    target = lineage_store.get(version_id)
    if target is None or not target["promoted_at"]:
        raise ValueError("can only roll back to a version that was the reference before")
    old = lineage_store.reference()
    db.update("versions", version_id, status="reference", promoted_at=db.now())
    db.update("versions", old["id"], status="retired")
    db.log("rollback", version_id, f"reference {old['label']} -> {target['label']}. {note}".strip())
