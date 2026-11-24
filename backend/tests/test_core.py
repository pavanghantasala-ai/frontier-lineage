from lineage import config, evals, grading
from lineage.providers import get_models
from lineage.retrieval import get_index


def test_validate_patch_clamps_and_rejects():
    clean, errors = config.validate_patch({"retrieval.top_k": 99, "prompt.quote_first": True, "nope.x": 1})
    assert clean["retrieval.top_k"] == config.RANGES["retrieval.top_k"][1]
    assert clean["prompt.quote_first"] is True
    assert "nope.x" not in clean and errors


def test_apply_patch_and_diff():
    new = config.apply_patch(config.DEFAULT_CONFIG, {"retrieval.contextual_chunks": True})
    assert config.DEFAULT_CONFIG["retrieval"]["contextual_chunks"] is False
    assert config.config_diff(config.DEFAULT_CONFIG, new) == [
        {"path": "retrieval.contextual_chunks", "from": False, "to": True}]


def test_retrieval_finds_relevant_doc():
    hits = get_index(120, False).search("per diem meals travel", 3)
    assert any("travel" in h.doc_id for h in hits)


def test_grading_facts_and_abstain():
    task = {"facts": [["75"], ["receipt", "receipts"]]}
    ok = grading.grade(task, {"answer": "Meals are capped at $75 and need receipts.", "context": "capped at $75 receipts"})
    assert ok["correct"]
    bad = grading.grade(task, {"answer": "Meals are capped at $175.", "context": ""})
    assert not bad["correct"]
    ab = grading.grade({"expect_abstain": True, "facts": []}, {"answer": "The documents do not contain that.", "context": ""})
    assert ab["correct"] and ab["abstained"]


def test_mock_suite_is_deterministic():
    m = get_models(["mock-mid"])[0]
    tasks = evals.load_tasks()[:8]
    a = evals.run_suite(config.DEFAULT_CONFIG, m, runs=1, tasks=tasks)[0]
    b = evals.run_suite(config.DEFAULT_CONFIG, m, runs=1, tasks=tasks)[0]
    assert a == b
    assert 0 <= a["accuracy"] <= 1


def test_paired_delta_ci():
    p = {"per_task": {str(i): {"correct_rate": 0.0} for i in range(20)}}
    c = {"per_task": {str(i): {"correct_rate": 1.0 if i < 15 else 0.0} for i in range(20)}}
    d = evals.paired_delta(p, c)
    assert abs(d["delta"] - 0.75) < 1e-9 and d["ci_low"] > 0
    assert len(evals.regressions(c, p)) == 15
