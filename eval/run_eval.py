"""Benchmark runner (guide section 15.2). Not built yet: needs /qa/ask (build step 2).

Plan:
  - read eval/pq_benchmark.jsonl
    (one JSON object per line: id, house, date, question, official_answer,
     expected_numbers [{"value": ..., "unit": ...}], topic)
  - ask each question through the API
  - numeric accuracy: system numbers vs expected_numbers (within 0.5%)
  - grounded %, average latency
  - save results with the run date for the Metrics screen
"""

if __name__ == "__main__":
    raise SystemExit("run_eval.py is not built yet (needs the Q&A endpoint).")
