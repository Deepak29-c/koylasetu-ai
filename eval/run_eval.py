"""Benchmark runner (guide section 15.2, issue #11): ask the past Parliament questions in
eval/pq_benchmark.jsonl through the running API and measure how often the answer has the
official figures, how often it is grounded, and how fast it comes back.

Run from the repo root with the backend venv, API running and a demo analyst seeded:

    backend/.venv/Scripts/python eval/run_eval.py                 # all questions
    backend/.venv/Scripts/python eval/run_eval.py --limit 5 --timeout 60
    backend/.venv/Scripts/python eval/run_eval.py --ids LS-2018-12-26-U2431,LS-2019-01-02-U3597
    backend/.venv/Scripts/python eval/run_eval.py --base-url http://localhost:8000 \
        --database-url postgresql+psycopg://koyla:koyla@localhost:5432/koyla   # + automation %
    backend/.venv/Scripts/python eval/run_eval.py --rescore eval/results/2026-09-26   # after
        filling citation_check.csv (or with --time-trials trials.csv)

Results go to eval/results/<run date>/. The logic and the exact metric definitions are in
scripts/benchmark_runner.py (kept there so CI lints and tests it).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from benchmark_runner import main  # noqa: E402

if __name__ == "__main__":
    main()
