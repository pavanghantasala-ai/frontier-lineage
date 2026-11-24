from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, decisions, frontier_diff, lineage_store, pipeline, scout
from .adversary import WEEKLY_BUDGET_USD, spend_this_week
from .config import KNOBS
from .evals import load_tasks
from .paths import WEB_DIST
from .providers import available_models, default_eval_models, load_specs

app = FastAPI(title="Frontier Lineage")


class CycleReq(BaseModel):
    models: list[str] | None = None
    runs: int = 2
    max_cards: int = 3
    live: bool = False
    seeds: bool = True


class DecisionReq(BaseModel):
    action: str
    note: str = ""


class RollbackReq(BaseModel):
    version_id: int
    note: str = ""


class IngestReq(BaseModel):
    url: str
    lab: str = "Manual"


@app.on_event("startup")
def _startup():
    lineage_store.reference()


@app.get("/api/status")
def status():
    avail = {m.id for m in available_models()}
    return {
        "models": [{**{k: s[k] for k in ("id", "provider", "model")}, "available": s["id"] in avail,
                    "mock": s["provider"] == "mock"} for s in load_specs()],
        "default_models": [m.id for m in default_eval_models()],
        "cycle": pipeline.STATUS,
        "reference": lineage_store.reference()["label"],
        "spend_usd": spend_this_week(), "budget_usd": WEEKLY_BUDGET_USD,
        "n_tasks": len(load_tasks()),
        "counts": {t: db.one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in ("items", "cards", "versions", "verdicts")},
    }


@app.post("/api/cycle")
def start_cycle(req: CycleReq):
    if pipeline.STATUS["running"]:
        raise HTTPException(409, "a cycle is already running")
    try:
        if req.models:
            from .providers import get_models
            get_models(req.models)
    except ValueError as e:
        raise HTTPException(400, str(e))
    pipeline.run_cycle_async(models=req.models, runs=max(1, min(5, req.runs)), max_cards=max(1, min(10, req.max_cards)),
                             live=req.live, seeds=req.seeds)
    return {"started": True}


@app.get("/api/items")
def items():
    return db.q("SELECT id, source, lab, title, url, published, fetched_at, status FROM items ORDER BY id DESC")


@app.post("/api/ingest")
def ingest(req: IngestReq):
    try:
        return {"item_id": scout.ingest_url(req.url, req.lab)}
    except Exception as e:
        raise HTTPException(400, f"could not fetch {req.url}: {e}")


@app.get("/api/cards")
def cards():
    rows = db.q("SELECT * FROM cards ORDER BY id DESC")
    verdicts = {v["card_id"]: v for v in db.q("SELECT id, card_id, verdict, decision, published FROM verdicts")}
    return [{**r, "verdict": verdicts.get(r["id"])} for r in rows]


@app.get("/api/cards/{card_id}")
def card(card_id: int):
    row = db.one("SELECT * FROM cards WHERE id=?", (card_id,))
    if not row:
        raise HTTPException(404)
    item = db.one("SELECT id, lab, title, url, published, text FROM items WHERE id=?", (row["item_id"],))
    verdict = db.one("SELECT * FROM verdicts WHERE card_id=? ORDER BY id DESC", (card_id,))
    return {**row, "item": item, "verdict": verdict}


@app.get("/api/versions")
def versions():
    return lineage_store.tree()


@app.get("/api/versions/{version_id}")
def version(version_id: int):
    v = lineage_store.get(version_id)
    if not v:
        raise HTTPException(404)
    ev = db.q("SELECT id, model_id, runs, metrics, samples, cost_usd, created_at FROM evals WHERE version_id=?", (version_id,))
    return {**v, "evals": ev}


@app.get("/api/scoreboard")
def scoreboard():
    cards_by_id = {c["id"]: c["data"] for c in db.q("SELECT id, data FROM cards")}
    out = []
    for v in db.q("SELECT * FROM verdicts WHERE published=1 ORDER BY decided_at DESC"):
        out.append(frontier_diff._card_view(v, cards_by_id) | {"decided_at": v["decided_at"]})
    return out


@app.get("/api/diff")
def diff(week: str | None = None):
    return frontier_diff.build(week)


@app.get("/api/diff/markdown", response_class=PlainTextResponse)
def diff_md(week: str | None = None):
    return frontier_diff.markdown(week)


@app.post("/api/verdicts/{verdict_id}/decision")
def decision(verdict_id: int, req: DecisionReq):
    try:
        decisions.decide(verdict_id, req.action, req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/rollback")
def rollback(req: RollbackReq):
    try:
        decisions.rollback(req.version_id, req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/api/ledger")
def ledger():
    return db.q("SELECT * FROM ledger ORDER BY id DESC LIMIT 200")


@app.get("/api/knobs")
def knobs():
    return [{"knob": k, "type": t.__name__, "description": d} for k, (t, d) in KNOBS.items()]


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = WEB_DIST / path
        return FileResponse(f if path and f.is_file() else WEB_DIST / "index.html")
