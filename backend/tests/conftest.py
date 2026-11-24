import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    from lineage import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db", raising=False)
    os.environ["LINEAGE_DB"] = str(tmp_path / "t.db")
    db.reset()
    yield
