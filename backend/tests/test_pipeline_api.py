from fastapi.testclient import TestClient

from lineage import adversary, pipeline


def _cycle():
    return pipeline.run_cycle(models=["mock-strong", "mock-mid", "mock-weak"], runs=1, max_cards=6, live=False, seeds=True)


def test_judge_thresholds():
    card = {"min_delta": 0.03}
    good = {"accuracy": {"delta": 0.1, "ci_low": 0.02}, "groundedness_delta": 0.0, "cost_increase": 0.1}
    weak = {"accuracy": {"delta": 0.05, "ci_low": -0.01}, "groundedness_delta": 0.0, "cost_increase": 0.1}
    bad = {"accuracy": {"delta": -0.05, "ci_low": -0.1}, "groundedness_delta": 0.0, "cost_increase": 0.1}
    assert adversary.judge(card, {"a": dict(good), "b": dict(good)})[0] == "Replicated"
    assert adversary.judge(card, {"a": dict(good), "b": dict(bad)})[0] == "Partial"
    assert adversary.judge(card, {"a": dict(weak), "b": dict(bad)})[0] == "Partial"
    assert adversary.judge(card, {"a": dict(bad), "b": dict(bad)})[0] == "Didn't hold"
    costly = dict(good, cost_increase=5.0)
    assert adversary.judge(card, {"a": costly, "b": dict(costly)})[0] == "Didn't hold"


def test_write_actions_need_operator(monkeypatch):
    from lineage.api import app
    with TestClient(app) as client:
        assert client.post("/api/rollback", json={"version_id": 1}).status_code == 403
        monkeypatch.setenv("LINEAGE_ADMIN_TOKEN", "t0ken")
        assert client.post("/api/cycle", json={}, headers={"X-Admin-Token": "wrong"}).status_code == 401
        assert client.get("/api/status").status_code == 200


def test_full_loop_and_human_gate(monkeypatch):
    monkeypatch.setenv("LINEAGE_ADMIN_TOKEN", "t0ken")
    from lineage.api import app
    with TestClient(app, headers={"X-Admin-Token": "t0ken"}) as client:
        _cycle()
        diff = client.get("/api/diff").json()
        assert len(diff["shipped"]) >= 6
        assert diff["pending"], "cycle should produce verdicts awaiting a human"
        assert client.get("/api/scoreboard").json() == []

        v = diff["pending"][0]
        assert client.post(f"/api/verdicts/{v['verdict_id']}/decision", json={"action": "publish"}).status_code == 200
        assert len(client.get("/api/scoreboard").json()) == 1
        assert client.post(f"/api/verdicts/{v['verdict_id']}/decision", json={"action": "bogus"}).status_code == 400

        rep = [x for x in client.get("/api/diff").json()["pending"] if x["verdict"] == "Replicated"]
        if rep:
            r = client.post(f"/api/verdicts/{rep[0]['verdict_id']}/decision", json={"action": "promote"})
            assert r.status_code == 200
            status = client.get("/api/status").json()
            assert status["reference"] != "v0"
            assert client.post("/api/rollback", json={"version_id": 1}).status_code == 200
            assert client.get("/api/status").json()["reference"] == "v0"

        md = client.get("/api/diff/markdown").text
        assert "Frontier Diff" in md
        assert client.get("/api/ledger").json()


def test_public_export_is_read_only_snapshot(tmp_path):
    import json
    from lineage import db, export
    _cycle()
    db.conn().execute("UPDATE items SET text = 'FULL ARTICLE BODY'"); db.conn().commit()
    db.log("decision", 1, "publish: SECRET OPERATOR NOTE")
    out = export.export(tmp_path / "data")
    status = json.loads((out / "status.json").read_text())
    assert status["cycle"]["log"] == [] and {m["id"] for m in status["models"]} <= {"mock-strong", "mock-mid", "mock-weak"}
    card_files = list((out / "cards").glob("*.json"))
    assert card_files and all("FULL ARTICLE BODY" not in f.read_text() for f in card_files)
    assert "FULL ARTICLE BODY" not in (out / "items.json").read_text()
    assert "SECRET OPERATOR NOTE" not in (out / "ledger.json").read_text()
    for name in ("diff", "scoreboard", "versions", "ledger"):
        assert (out / f"{name}.json").exists()
