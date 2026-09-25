# KoylaSetu AI

Verified AI Reporting & Parliamentary-Reply Assistant for CMPDI / CIL (SIH 2026, problem 26023).

**Core rule:** numbers come from the database, words come from the AI, and every figure has a source.
The full technical spec is [docs/KoylaSetu_AI_Developer_Guide.docx](docs/KoylaSetu_AI_Developer_Guide.docx).

**New to the project? Start with [docs/SETUP.md](docs/SETUP.md)** for prerequisites, first-time setup and common problems.
**Picking up existing work? Read [docs/KNOWLEDGE_TRANSFER.md](docs/KNOWLEDGE_TRANSFER.md)** for what's actually built vs. stubbed, the data model, the non-Docker setup gotchas, and where to pick up next.

## What's in the repo

| Path | What |
|---|---|
| `docker-compose.yml` | db (Postgres 16 + pgvector), redis, ollama, api, worker, web |
| `backend/app` | FastAPI: `core/` (config, JWT, RBAC), `models/`, `schemas/`, `api/`, `services/`, `llm/` |
| `backend/worker` | RQ jobs: ingest, extract, validate, embed, topics |
| `backend/alembic` | DB migrations |
| `frontend/` | Next.js (app router) + Tailwind |
| `eval/` | Benchmark set + runner |
| `data/` | Downloaded public documents (git-ignored, except `sources.csv`) |

## Status

Built so far:

**PQ reply first draft** (guide 10.1-10.2), "New PQ reply" screen:
- `POST /pq-replies/draft` (Analyst / Approver): paste house, question no., date, MP, subject
  and question text; it is saved as a `parliament_questions` row and split into parts on
  (a), (b)… / a), b)…, (क), (ख)… or (i), (ii)… (the local model splits it only when there
  are no markers, and its parts must be exact copies from the question). The model is
  checked first; if it is not there, nothing is saved (503). An `Idempotency-Key` header
  makes a retry return the draft already made
- Each part is answered through the Q&A service (`qa.ask`), so the same retrieval, routing
  and grounding rules apply. Then, stricter than the Ask screen: every sentence with a figure
  must cite a source and the figure must be in the source it cites (the MP's question does
  not count, although it often states figures); other sentences are dropped and their
  figures listed on the part. A part with no source says "Information not found in
  available documents"
- Grounding limits (from `services/grounding.py`): numbers written as words are not checked,
  units are not compared (12.16 MT passes against "12.16 lakh tonnes"), and a small number
  can match part of a token ("24" in "2023-24")
- Saved as a DRAFT `pq_reply` report: `content_json` has the header, one block per part
  `{part, text, table, citations}`, a reply-wide sources list (S1, S2…: document + page)
  and a plain `text` rendering for the report editor; tables with more than 6 rows become
  Annexure-I, II…; every source is a `report_citations` row pointing at its fact or chunk
- `GET /reports/{id}/export?format=docx|pdf` (export permission): official layout (Ministry
  header, house, Starred/Unstarred Question No., date, subject, MP and parts, ANSWER, Minister
  line placeholder, "A Statement is laid on the Table" + Statement for starred questions,
  answers, annexures, internal sources list). DOCX via python-docx, PDF via PyMuPDF (Hindi
  renders); unapproved reports carry a DRAFT line, warnings and removed-figure notes. A reply
  edited in the plain-text editor is exported from its text without repeating the header or
  sources. Nothing is sent anywhere

**Step 2: Q&A with citations** (guide section 9, text route), Ask screen + document viewer:
- Hybrid search: Postgres full-text + pgvector (BGE-M3), merged with reciprocal rank fusion,
  always filtered to the user's org unit; top 6 passages
- The local model answers only from those passages (guide 9.2 prompt, temperature 0.1) and
  cites them as [C1]…; loose citation styles from small models are normalised
- Grounding check: every number and date in the answer must appear in the passages or the
  question (±0.5%, dates exact); unsupported values are listed and shown in red
- Confidence: high = grounded + cited, medium = grounded but uncited / not found, low = a value
  not in the sources. It says the figures are in the cited text, not that the right row was used
- Tables are stored as row grids (`| NCL | 12.16 | 12.70 |`) so the model can see columns
- Every answer is logged in `qa_logs`; thumbs up/down feedback
- Clicking a source opens the page image with the passage highlighted; Viewer/Approver can
  open cited pages even though they can't browse the document list
- Guard: the model server must be local unless `ALLOW_EXTERNAL_CALLS=true`

Measured on the demo PC (CPU only, `qwen2.5:3b-instruct`): about 30-55 s per answer.
Questions that need a figure from a table cell (e.g. "NCL production vs target") are not
reliable on the text route with the 3B model; they go to the NUMERIC route (SQL on verified
facts), built in step 3.

**W1 ingestion pipeline** (guide 7.1 steps 1-9), runs in the worker:
- PDF pages with a text layer: text blocks with position (bbox) + ruled tables, cells copied as text
- Scanned pages and images (PNG/JPG/multi-page TIFF): Tesseract OCR, Hindi + English, with
  per-page confidence; sideways pages (e.g. landscape charts) are detected and rotated
- Excel/CSV: every sheet is a table; Word: paragraphs + tables
- Text split into chunks of up to ~350 words that never cross a page, so every chunk can be
  cited as (document, page) and highlighted
- Embeddings (BGE-M3) via the local model server; if Ollama is not running, chunks are
  saved without embeddings and keyword search still works
- Live progress (pages done / total); retry re-runs any finished document
- `GET /documents/{id}/pages/{n}` (chunks + tables with boxes) and `/pages/{n}/image`

**Tables → facts** (guide 7.2-7.4, step 10), runs in the same job:
- Every number in a table becomes a fact: metric, subsidiary or state, period (FY or month),
  category (Measured / Indicated / Inferred), value, unit, and its document, page and cell box
- Read from the column header, row label and the title just above the table; handles merged
  header cells, serial-number columns and sub-headers PyMuPDF puts inside the first data row
- Units converted to MT / Mcum (lakh, thousand, million tonnes; cum), original unit kept;
  subsidiary aliases (Mahanadi Coalfields / M.C.L. → MCL), FY and month forms, Hindi digits
- Skipped on purpose rather than stored with the wrong meaning: %, growth, money and count
  columns; "upto" / Apr-Nov ranges and projections; single mines, sectors, coal grades and
  depth ranges; lignite; and any fact a table gives twice with different values
- Confidence = OCR confidence × header mapping × 0.5 if the unit was not stated (guide 7.4);
  the local LLM only names a table's metric when no keyword matches (`EXTRACT_USE_LLM`)
- `GET /documents/{id}/facts`; `python -m worker.extract <document id>` rebuilds the facts
  of a document processed before this existed

**Topic explorer** (guide 11, Module E), Topics screen:
- Processed PQ answer documents (`pq_answer`) are read into `parliament_questions`: house,
  starred/unstarred, number, answer date, subject, MPs, question and parts, parsed from the
  text (tolerates OCR slips; Hindi headers understood)
- Cleaning: English + Hindi (Devanagari) words, numbers/punctuation dropped, English, Hindi and
  PQ-wording stopwords (ministry, whether, details, state-wise, coal, …)
- Topics: TF-IDF over words and two-word phrases + NMF (scikit-learn), deterministic; label =
  top keywords; counts per year and per session (Budget / Monsoon / Winter); a small Hindi →
  English glossary lets Hindi questions join the English topic
- Word cloud as JSON (drawn in the browser), filtered by house / years / session / subsidiary,
  from questions and/or org-scoped document text, cached by filter
- Worker job on the `topics` queue: queued after every processed PQ document, re-builds when
  `TOPICS_MIN_NEW_PQS` (default 5) new questions arrived; admin "Re-run" button
  (`POST /topics/refresh`); by hand `python -m worker.topics --force`
- `GET /topics/wordcloud?house=LS&from=2019&to=2025`, `GET /topics`, `GET /topics/{id}/questions`

**Benchmark set** (guide 15.2, issue #16): `eval/pq_benchmark.jsonl` holds 34 real Lok Sabha
coal questions (2018-2022) with the official written answer, the key figures in it (183 in
all: value, unit and, for figures from tables or easy to confuse, an optional `label`), a topic
and the coal.gov.in PDF it came from. Units come from one fixed list (MT, MTPA, MT/day,
thousand tonnes, tonnes/year, tonnes/day, rakes/day, BU, MW, GW, %, Rs crore, Rs/tonne, days,
years, count). Only PDFs with a clean text layer were used; scanned ones and ones with a
garbled OCR layer were skipped. `python scripts/check_benchmark.py` (also run by pytest)
checks the format `eval/run_eval.py` expects, the units, and that every expected value occurs
in its official answer as a standalone number with the right sign. It does not check the unit
or which cell was meant.

**Benchmark runner** (guide 15.2, issue #11): with the API running and the demo users seeded,
`backend/.venv/Scripts/python eval/run_eval.py` (options `--limit N`, `--ids a,b`,
`--base-url`, `--timeout`, `--database-url` for automation %) logs in as the demo analyst,
asks every benchmark question through `POST /qa/ask` and writes `eval/results/<date>/`:
`report.md` and `summary.json` (numeric accuracy = expected figures found within 0.5% after
unit conversion ÷ all expected figures, also per topic and per question; questions with every
figure right; grounded %; not-found and error counts; latency p50/avg/max; figures in the
answer that are not in the official answer), plus `results.json` and `citation_check.csv`
(git-ignored: they hold text from our documents). Timeouts, 503s and other API errors are
recorded and the run goes on. Citation correctness is a manual check: fill the `correct`
column of `citation_check.csv` with Y/N, then `run_eval.py --rescore eval/results/<date>`;
time saved comes from timed trials (`--time-trials`, CSV id, manual_seconds,
assisted_seconds). Exact metric definitions: `scripts/benchmark_runner.py`. Real accuracy
numbers need the local models pulled and the source documents loaded.

**Setup (step 0):**
- Docker Compose for all 6 services
- All tables from guide section 6, plus the first Alembic migration
- Login with JWT access and refresh tokens (argon2 password hashing); `/me`
- RBAC matrix from guide 2.1, checked on every endpoint; org-unit scoping in queries
- Document upload: file type checked by content, 100 MB limit, sha256 duplicate check, audit log, ingest job queued
- Document list, detail and retry endpoints
- Starter corpus: `scripts/load_sources.py` uploads every document in `data/sources.csv`
  (optional `title` upload field, single file only, keeps the official title)
- Frontend: login, home, upload (drag and drop, progress bar) and documents pages, with an English/Hindi toggle
- Seed script with demo users for all 6 roles

Not built yet: validation rules + review queue + NUMERIC route (rest of step 3), reports,
and the Metrics screen that shows the benchmark results. Tables on scanned pages are not detected yet (OCR gives text only).
PaddleOCR (`OCR_ENGINE=paddle`) currently falls back to Tesseract.

## Run with Docker (the normal way)

```bash
cp .env.example .env          # then change JWT_SECRET and SEED_DEMO_PASSWORD
docker compose up -d --build
docker exec ollama ollama pull bge-m3                # embeddings, ~1.2 GB, once
docker exec ollama ollama pull qwen2.5:3b-instruct   # answers, ~2 GB, once
docker exec koyla-api python -m app.scripts.seed
```

The model name lives in `.env` (`LLM_MODEL`). Use `qwen2.5:7b-instruct` on a machine with a
GPU or 16 GB+ RAM given to Docker (guide 4.3). After pulling `bge-m3` for the first time,
embed chunks that were processed before it existed:
`docker exec koyla-worker python -c "from worker.embed import embed_missing; print(embed_missing())"`

Web: http://localhost:3000 · API docs: http://localhost:8000/docs

Demo logins (password = `SEED_DEMO_PASSWORD`): `admin@`, `operator@`, `reviewer@`, `analyst@`,
`approver@`, `viewer@` + `koylasetu.local`.

## Run without Docker

Postgres 16 + pgvector and Redis on your own machine, no Docker. On macOS / Ubuntu / Debian:

```bash
bash scripts/setup_local.sh --seed       # installs + starts services, creates DB, migrates, seeds
```

Windows steps (pgvector build, Redis via Memurai / WSL) and what each step does are in
[docs/SETUP.md, section 9](docs/SETUP.md#9-run-without-docker). After pulling new code, re-run
`scripts/setup_local_db.py`; it only does what is missing. Then:

```bash
cd backend
.venv/Scripts/uvicorn app.main:app --reload       # Linux/macOS: .venv/bin/uvicorn
.venv/bin/rq worker ingest topics reports          # worker (macOS/Linux; Windows: see SETUP.md)
```

```bash
cd frontend
npm install
npm run dev
```

**Windows note:** if Smart App Control blocks SQLAlchemy's compiled files ("An Application Control
policy has blocked this file"), reinstall it as pure Python inside the venv:
`DISABLE_SQLALCHEMY_CEXT=1 .venv/Scripts/pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy`

## Public source documents

We build and test only on real public government documents, never made-up figures.
Download them (about 50 MB, needs internet, Python 3 standard library only):

```bash
python scripts/fetch_sources.py
```

Files go to `data/raw/` (git-ignored). Each file is recorded in `data/sources.csv` with its
official URL, publisher, download date and sha256. Safe to re-run: it skips files it already has.
Current set (100 files, 99 distinct: two PQ URLs serve the same file): 5 key documents (CMPDI
coal inventories, Monthly Coal Statistics, Ministry annual report chapter, one PQ answer),
2 CEA monthly coal statements for thermal power stations (.xls, National Power Portal) and
93 Lok Sabha PQ answers from the Ministry of Coal archive, 9 of them scanned (no text layer,
need OCR). If downloads fail with `CERTIFICATE_VERIFY_FAILED` because your network re-signs
HTTPS, point `SSL_CERT_FILE` at that CA bundle; never turn verification off.

Then load them into a running API (issue #15). Each file is uploaded through the normal
upload endpoint with its doc type, FY, official title and source URL, marked public, so the
default login is the demo admin (only CIL HQ / Ministry / Admin may mark documents public):

```bash
python scripts/load_sources.py --api http://localhost:8000      # all downloaded files
python scripts/load_sources.py --doc-type coal_inventory --dry-run
```

It prints `created / duplicate / rejected / missing file / error` per file and in total, and
exits 1 if any upload failed, the API cannot be reached, or nothing was loaded because the
files were never downloaded. Safe to re-run: the API recognises files it already has by sha256
and reports them as duplicates. A duplicate is not changed: it keeps the visibility (public or
not), title and metadata of its first upload.
Password: set `KOYLA_PASSWORD` (keeps it out of shell history); `--password` also works, then
`SEED_DEMO_PASSWORD`, else the seed default.

## Checks

```bash
cd backend && ruff check . && black --check . && pytest -q
cd frontend && npm run lint && npm run build
```

## Git workflow

`main` = demo-ready, `dev` = integration, feature branches like `feat/qa-grounding`.
Every change goes through a PR with one reviewer. Never commit `.env`, data files or model files.
