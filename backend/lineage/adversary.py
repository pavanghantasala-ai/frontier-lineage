"""Adversary: tries to break a card's claim across models at real cost, against the pre-registered test."""
from datetime import datetime, timezone

from . import db, evals, lineage_store

WEEKLY_BUDGET_USD = 25.0


def iso_week(ts=None):
    d = datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def spend_this_week():
    week = iso_week()
    return sum(e["cost_usd"] or 0 for e in db.q("SELECT cost_usd, created_at FROM evals") if iso_week(e["created_at"]) == week)


def estimate_cost(parent, models, runs):
    est = 0.0
    for m in models:
        cached = db.one("SELECT metrics FROM evals WHERE version_id=? AND model_id=? ORDER BY id DESC", (parent["id"], m.id))
        per_task = cached["metrics"]["cost_per_task"] if cached else 0.003
        n = len(evals.load_tasks()) * runs
        est += per_task * n * (2.5 if not cached else 1.5)
    return est


def judge(card, comparisons):
    """Apply the card's pre-registered thresholds. comparisons: {model_id: {...}}."""
    min_delta = card.get("min_delta", 0.03)
    passed, positive, negative = [], [], []
    for mid, c in comparisons.items():
        guards_ok = (c["groundedness_delta"] >= -card.get("max_groundedness_drop", 0.03)
                     and c["cost_increase"] <= card.get("max_cost_increase", 1.0))
        c["guards_ok"] = guards_ok
        if c["accuracy"]["delta"] >= min_delta and guards_ok:
            positive.append(mid)
            if c["accuracy"]["ci_low"] > 0:
                passed.append(mid)
        if c["accuracy"]["delta"] < 0:
            negative.append(mid)
    need = min(2, len(comparisons))
    if len(passed) >= need:
        verdict = "Replicated"
    elif positive:
        verdict = "Partial"
    else:
        verdict = "Didn't hold"
    return verdict, {"passed": passed, "positive": positive, "negative": negative,
                     "model_specific": bool(positive) and bool(negative), "required_models": need}


def test_card(card_row, candidate, models, runs, log=print):
    card = card_row["data"]
    parent = lineage_store.get(candidate["parent_id"])
    est = estimate_cost(parent, models, runs)
    if spend_this_week() + est > WEEKLY_BUDGET_USD:
        log(f"adversary: skipping card {card_row['id']}, estimated ${est:.2f} would exceed the weekly budget")
        db.update("cards", card_row["id"], status="budget_skipped")
        return None
    comparisons = {}
    for m in models:
        log(f"adversary: {candidate['label']} vs {parent['label']} on {m.id}")
        pe = evals.eval_version(parent, m, runs)
        ce = evals.eval_version(candidate, m, runs)
        pm, cm = pe["metrics"], ce["metrics"]
        comparisons[m.id] = {
            "accuracy": evals.paired_delta(pe, ce),
            "parent_accuracy": pm["accuracy"], "candidate_accuracy": cm["accuracy"],
            "by_type": {k: cm["accuracy_by_type"].get(k, 0) - v for k, v in pm["accuracy_by_type"].items()},
            "groundedness_delta": cm["groundedness"] - pm["groundedness"],
            "cost_per_task": cm["cost_per_task"], "parent_cost_per_task": pm["cost_per_task"],
            "cost_increase": (cm["cost_per_task"] / pm["cost_per_task"] - 1) if pm["cost_per_task"] else 0.0,
            "p95_latency_ms": cm["p95_latency_ms"], "parent_p95_latency_ms": pm["p95_latency_ms"],
            "errors": cm["errors"] + pm["errors"],
            "regressions": evals.regressions(pe, ce),
            "mock": m.is_mock,
        }
    verdict, summary = judge(card, comparisons)
    details = {"comparisons": comparisons, "summary": summary, "runs": runs, "models": [m.id for m in models],
               "test": {k: card.get(k) for k in ("primary_metric", "min_delta", "max_groundedness_drop", "max_cost_increase")}}
    vid = db.insert("verdicts", card_id=card_row["id"], version_id=candidate["id"], parent_id=parent["id"], verdict=verdict,
                    details=details, created_at=db.now())
    db.update("cards", card_row["id"], status="tested")
    db.log("verdict", vid, f"{verdict}: {card.get('title')} ({candidate['label']} vs {parent['label']})")
    return vid
