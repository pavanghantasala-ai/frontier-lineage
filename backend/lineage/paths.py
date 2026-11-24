import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CORPUS = DATA / "corpus"
TASKS = DATA / "tasks.jsonl"
MODELS = DATA / "models.json"
SOURCES = DATA / "sources.json"
SEEDS = DATA / "seed_items.json"
DB_PATH = Path(os.environ.get("LINEAGE_DB", ROOT / "state" / "lineage.db"))
WEB_DIST = ROOT.parent / "web" / "dist"
