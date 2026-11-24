"""One cycle of the loop: Scout -> Extractor -> Replicator -> Adversary. Humans decide in the Frontier Diff."""
import threading

from . import db, extractor, lineage_store, scout
from .adversary import over_budget, test_card
from .providers import default_eval_models, get_models, healthy

STATUS = {"running": False, "log": [], "error": None}
_lock = threading.Lock()


def _log(msg):
    STATUS["log"].append(f"{db.now()} {msg}")
    STATUS["log"] = STATUS["log"][-200:]
    print(msg, flush=True)


def run_cycle(models=None, runs=2, max_cards=3, live=False, seeds=True, max_extract=15):
    with _lock:
        if STATUS["running"]:
            raise RuntimeError("a cycle is already running")
        STATUS.update(running=True, log=[], error=None)
    try:
        ms = healthy(get_models(models) if models else default_eval_models(), log=_log)
        if not ms:
            raise RuntimeError("no working models: check API keys and credit")
        _log(f"cycle: models={[m.id for m in ms]} runs={runs} live={live}")
        lineage_store.reference()
        if seeds:
            _log(f"scout: {len(scout.scout_seeds())} seed items added")
        if live:
            _log(f"scout: {len(scout.scout_live(log=_log))} live items added")
        extractor.reset_failures()
        new_items = db.q("SELECT * FROM items WHERE status='new' ORDER BY id LIMIT ?", (max_extract,))
        for item in new_items:
            extractor.extract_item(item, log=_log)
        ready = db.q("SELECT * FROM cards WHERE status='ready'")
        ready.sort(key=lambda c: (-(c["data"].get("expected_impact") or 0), c["id"]))
        tested = 0
        for card in ready:
            if tested >= max_cards:
                break
            if over_budget(lineage_store.reference(), ms, runs):
                _log("adversary: weekly budget reached; remaining cards stay queued for next week")
                break
            cand = lineage_store.replicate(card["id"])
            if cand is None:
                _log(f"replicator: card {card['id']} skipped ({db.one('SELECT status FROM cards WHERE id=?', (card['id'],))['status']})")
                continue
            card = db.one("SELECT * FROM cards WHERE id=?", (card["id"],))
            if test_card(card, cand, ms, runs, log=_log):
                tested += 1
        _log(f"cycle: done, {tested} cards tested")
    except Exception as e:
        STATUS["error"] = str(e)
        _log(f"cycle failed: {e}")
        raise
    finally:
        STATUS["running"] = False


def run_cycle_async(**kwargs):
    t = threading.Thread(target=lambda: _safe(kwargs), daemon=True)
    t.start()


def _safe(kwargs):
    try:
        run_cycle(**kwargs)
    except Exception:
        pass
