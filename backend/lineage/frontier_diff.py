"""The Frontier Diff: one auto-generated page for the weekly human gate."""
from . import db
from .adversary import WEEKLY_BUDGET_USD, iso_week, spend_this_week


def _card_view(v, cards):
    card = cards.get(v["card_id"], {})
    comps = v["details"]["comparisons"]
    return {
        "verdict_id": v["id"], "verdict": v["verdict"], "decision": v["decision"], "published": bool(v["published"]),
        "card_id": v["card_id"], "title": card.get("title"), "lab": card.get("lab"), "url": card.get("url"),
        "claim": card.get("claim"), "config_patch": card.get("config_patch"), "fidelity": card.get("fidelity"),
        "models": {mid: {"delta": c["accuracy"]["delta"], "ci_low": c["accuracy"]["ci_low"], "ci_high": c["accuracy"]["ci_high"],
                         "cost_increase": c["cost_increase"], "groundedness_delta": c["groundedness_delta"], "mock": c["mock"],
                         "regressions": len(c["regressions"])}
                   for mid, c in comps.items()},
        "summary": v["details"]["summary"], "version_id": v["version_id"], "parent_id": v["parent_id"],
    }


def build(week=None):
    week = week or iso_week()
    items = [i for i in db.q("SELECT id, lab, title, url, status, fetched_at FROM items ORDER BY id DESC") if iso_week(i["fetched_at"]) == week]
    cards = {c["id"]: c["data"] for c in db.q("SELECT id, data FROM cards")}
    verdicts = [_card_view(v, cards) for v in db.q("SELECT * FROM verdicts ORDER BY id DESC") if iso_week(v["created_at"]) == week]
    undecided = [_card_view(v, cards) for v in db.q("SELECT * FROM verdicts WHERE decision IS NULL ORDER BY id DESC")]
    ref = db.one("SELECT label FROM versions WHERE status='reference' ORDER BY promoted_at DESC, id DESC")
    mock = any(m["mock"] for v in verdicts for m in v["models"].values())
    return {
        "week": week,
        "reference": ref["label"] if ref else None,
        "mock": mock,
        "shipped": [{"lab": i["lab"], "title": i["title"], "url": i["url"], "status": i["status"]} for i in items],
        "replicated": [v for v in verdicts if v["verdict"] == "Replicated"],
        "partial": [v for v in verdicts if v["verdict"] == "Partial"],
        "didnt_hold": [v for v in verdicts if v["verdict"] == "Didn't hold"],
        "proposed_promotions": [v for v in undecided if v["verdict"] == "Replicated"],
        "pending": undecided,
        "spend_usd": spend_this_week(),
        "budget_usd": WEEKLY_BUDGET_USD,
    }


def _line(v):
    parts = [f"{mid} {m['delta'] * 100:+.1f} pts" for mid, m in v["models"].items()]
    return f"- **{v['lab']}: {v['title']}** ({v['url']}). Claim: {v['claim']} Result: {', '.join(parts)}."


def markdown(week=None):
    d = build(week)
    out = [f"# Frontier Diff, {d['week']}", ""]
    if d["mock"]:
        out += ["> Results in this issue come from the mock model, not real LLMs.", ""]
    out += ["## What shipped", ""] + [f"- {i['lab']}: [{i['title']}]({i['url']})" for i in d["shipped"]] + [""]
    for key, title in (("replicated", "Replicated"), ("partial", "Partly held"), ("didnt_hold", "Didn't hold")):
        out += [f"## {title}", ""] + ([_line(v) for v in d[key]] or ["- None this week."]) + [""]
    out += [f"Reference agent: {d['reference']}. Eval spend this week: ${d['spend_usd']:.2f} of ${d['budget_usd']:.0f}."]
    return "\n".join(out)
