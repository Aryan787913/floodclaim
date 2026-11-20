"""Grade every claim in data/claims.csv that has no result yet (saves to data/results.json).

Usage:  python scripts/grade_all.py           # only new / failed claims
        python scripts/grade_all.py --force   # re-grade everything
Run this BEFORE the demo so the dashboard opens instantly with all results ready.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import bq, pipeline  # noqa: E402

if __name__ == "__main__":
    n = pipeline.grade_pending(force="--force" in sys.argv)
    if bq.enabled():
        print("Writing to BigQuery ...")
        bq.wait()
        print("BigQuery:", bq.last_error or "ok")
    print(f"Done. Graded {n} claims.")
