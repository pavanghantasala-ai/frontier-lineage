import json
import random
from concurrent.futures import ThreadPoolExecutor
from statistics import mean

from . import agent, db, grading
from .paths import TASKS


def load_tasks():
    return [json.loads(line) for line in TASKS.read_text().splitlines() if line.strip()]


def p95(values):
    if not values:
        return 0.0
    v = sorted(values)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]


def run_suite(config, model, runs=2, tasks=None, workers=8):
    tasks = tasks or load_tasks()
    jobs = [(t, i) for t in tasks for i in range(runs)]

    def one(job):
        t, i = job
        try:
            r = agent.run(config, t["question"], model, seed_key=f"{t['id']}|{i}")
            g = grading.grade(t, r)
        except Exception as e:  # a failed call counts as a wrong, ungrounded answer
            r = {"answer": f"ERROR: {e}", "citations": [], "retrieved": [], "calls": 0, "input_tokens": 0,
                 "output_tokens": 0, "cost_usd": 0.0, "latency_ms": 0.0, "context": ""}
            g = {"correct": False, "grounded": 0.0, "abstained": False, "error": True}
        return t, i, r, g

    with ThreadPoolExecutor(max_workers=1 if model.is_mock else workers) as ex:
        results = list(ex.map(one, jobs))

    per_task, samples = {}, {}
    for t, i, r, g in results:
        pt = per_task.setdefault(t["id"], {"type": t["type"], "correct": [], "grounded": []})
        pt["correct"].append(int(g["correct"]))
        pt["grounded"].append(g["grounded"])
        if i == 0:
            samples[t["id"]] = {"question": t["question"], "answer": r["answer"][:800], "correct": g["correct"],
                                "retrieved": r["retrieved"]}
    for pt in per_task.values():
        pt["correct_rate"] = mean(pt.pop("correct"))
        pt["grounded"] = mean(pt["grounded"])

    by_type = {}
    for pt in per_task.values():
        by_type.setdefault(pt["type"], []).append(pt["correct_rate"])
    errors = sum(1 for *_, g in results if g.get("error"))
    metrics = {
        "accuracy": mean(pt["correct_rate"] for pt in per_task.values()),
        "accuracy_by_type": {k: mean(v) for k, v in by_type.items()},
        "groundedness": mean(pt["grounded"] for pt in per_task.values()),
        "cost_per_task": mean(r["cost_usd"] for *_, r, _ in results),
        "p95_latency_ms": p95([r["latency_ms"] for *_, r, _ in results]),
        "calls_per_task": mean(r["calls"] for *_, r, _ in results),
        "n_tasks": len(tasks),
        "runs": runs,
        "errors": errors,
    }
    total_cost = sum(r["cost_usd"] for *_, r, _ in results)
    return metrics, per_task, samples, total_cost


def eval_version(version, model, runs=2, force=False):
    if not force:
        cached = db.one("SELECT * FROM evals WHERE version_id=? AND model_id=? AND runs=? ORDER BY id DESC",
                        (version["id"], model.id, runs))
        if cached:
            return cached
    metrics, per_task, samples, cost = run_suite(version["config"], model, runs)
    eid = db.insert("evals", version_id=version["id"], model_id=model.id, runs=runs, metrics=metrics, per_task=per_task,
                    samples=samples, cost_usd=cost, created_at=db.now())
    return db.one("SELECT * FROM evals WHERE id=?", (eid,))


def paired_delta(parent_eval, cand_eval, metric="correct_rate", n_boot=2000, seed=7):
    """Mean per-task difference (candidate - parent) with a 95% paired bootstrap interval."""
    ids = sorted(set(parent_eval["per_task"]) & set(cand_eval["per_task"]))
    diffs = [cand_eval["per_task"][i][metric] - parent_eval["per_task"][i][metric] for i in ids]
    if not diffs:
        return {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}
    rng = random.Random(seed)
    boots = sorted(mean(rng.choice(diffs) for _ in diffs) for _ in range(n_boot))
    return {"delta": mean(diffs), "ci_low": boots[int(0.025 * n_boot)], "ci_high": boots[int(0.975 * n_boot) - 1], "n": len(diffs)}


def regressions(parent_eval, cand_eval):
    out = []
    for tid, c in cand_eval["per_task"].items():
        p = parent_eval["per_task"].get(tid)
        if p and c["correct_rate"] < p["correct_rate"]:
            out.append({"task_id": tid, "parent": p["correct_rate"], "candidate": c["correct_rate"]})
    return out
