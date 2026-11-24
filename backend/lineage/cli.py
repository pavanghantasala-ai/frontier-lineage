import argparse
import json

from . import db, frontier_diff, pipeline


def main():
    p = argparse.ArgumentParser(prog="lineage")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cycle", help="run Scout -> Extractor -> Replicator -> Adversary once")
    c.add_argument("--models", help="comma-separated model ids from data/models.json")
    c.add_argument("--runs", type=int, default=2)
    c.add_argument("--max-cards", type=int, default=3)
    c.add_argument("--live", action="store_true", help="fetch live lab sources")
    c.add_argument("--no-seeds", action="store_true")
    sub.add_parser("diff", help="print this week's Frontier Diff as Markdown")
    sub.add_parser("verdicts", help="list verdicts")
    sub.add_parser("reset", help="delete the local database")
    e = sub.add_parser("export", help="write a read-only JSON snapshot for the public site")
    e.add_argument("out", help="output directory, e.g. ../web/public/data")
    a = p.parse_args()
    if a.cmd == "cycle":
        pipeline.run_cycle(models=a.models.split(",") if a.models else None, runs=a.runs, max_cards=a.max_cards,
                           live=a.live, seeds=not a.no_seeds)
    elif a.cmd == "diff":
        print(frontier_diff.markdown())
    elif a.cmd == "verdicts":
        for v in db.q("SELECT id, card_id, verdict, decision, details FROM verdicts ORDER BY id"):
            print(json.dumps({"id": v["id"], "card": v["card_id"], "verdict": v["verdict"], "decision": v["decision"],
                              "deltas": {m: round(c["accuracy"]["delta"], 3) for m, c in v["details"]["comparisons"].items()}}))
    elif a.cmd == "reset":
        db.reset()
    elif a.cmd == "export":
        from .export import export
        print(f"wrote {export(a.out)}")


if __name__ == "__main__":
    main()
