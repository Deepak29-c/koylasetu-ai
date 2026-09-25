# KoylaSetu AI

Verified AI Reporting & Parliamentary-Reply Assistant for CMPDI / CIL (SIH 2026, problem 26023).

**Core rule:** numbers come from the database, words come from the AI, and every figure has a source.
The full technical spec is [docs/KoylaSetu_AI_Developer_Guide.docx](docs/KoylaSetu_AI_Developer_Guide.docx).

**New to the project? Start with [docs/SETUP.md](docs/SETUP.md)** for prerequisites, first-time setup and common problems.

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

**Step 3a: facts, validation, review queue** (guide 7.2-7.4, 8, W2):
- Tables → facts by keyword rules; numbers are copied from the cell by code, with the cell's
  bbox, so each figure can be highlighted on its page. Glued two-row headers are split,
  spanning headers filled across, stacked rows ("Jharkhand / Chhattisgarh") split
- Layouts supported today: subsidiary tables (production, coking coal, despatch, target;
  month / year-to-date / FY) and state-wise resource tables (Measured / Indicated / Inferred /
  Total, "as on" date, coking coal kept separate). Other tables produce no facts
- Normalisation: units → MT (lakh ×0.1, thousand ÷1000, billion ×1000) or Mcum, Indian/western
  digit grouping, Hindi digits, subsidiary and state aliases, month → YYYY-MM within the FY
- Confidence = cell confidence × header mapping × 0.5 if the unit was guessed; < 0.85 flagged
- Rules V01-V08 (totals, conflicts between documents, impossible values, unit, confidence,
  ±50 % year-on-year, duplicates, unknown period). Facts with no issue are accepted
  automatically; the rest go to the Reviewer. Document status NEEDS_REVIEW until resolved
- Review screen: source page with the cell highlighted, the value, why it was flagged, the
  other source's value; Accept / Correct / Reject (comment required for the last two), all
  logged in review_actions + audit_log. A reviewed document can no longer be re-processed
- `/review/summary` gives the automation % (facts accepted automatically ÷ all facts)

On the two documents processed so far (Monthly Coal Statistics Dec 2024, Coal Inventory 2025):
200 facts, 199 accepted automatically. That is 2 clean digital documents, not a benchmark result.

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

**Setup (step 0):**
- Docker Compose for all 6 services
- All tables from guide section 6, plus the first Alembic migration
- Login with JWT access and refresh tokens (argon2 password hashing); `/me`
- RBAC matrix from guide 2.1, checked on every endpoint; org-unit scoping in queries
- Document upload: file type checked by content, 100 MB limit, sha256 duplicate check, audit log, ingest job queued
- Document list, detail and retry endpoints
- Frontend: login, home, upload (drag and drop, progress bar) and documents pages, with an English/Hindi toggle
- Seed script with demo users for all 6 roles

Not built yet: NUMERIC route (step 3b), reports,
topics, and the benchmark. PaddleOCR (`OCR_ENGINE=paddle`) currently falls back to Tesseract.

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

You still need PostgreSQL 16 with the pgvector extension, and Redis, running locally.
Set `DATABASE_URL` / `REDIS_URL` in `.env` to `localhost`.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.scripts.seed
.venv/Scripts/uvicorn app.main:app --reload
.venv/Scripts/rq worker ingest topics reports      # worker, in another terminal
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
Current set: 5 key documents (CMPDI coal inventories, Monthly Coal Statistics, Ministry annual
report chapter, one PQ answer) + 93 Lok Sabha PQ answers from the Ministry of Coal archive.

## Checks

```bash
cd backend && ruff check . && black --check . && pytest -q
cd frontend && npm run lint && npm run build
```

## Git workflow

`main` = demo-ready, `dev` = integration, feature branches like `feat/qa-grounding`.
Every change goes through a PR with one reviewer. Never commit `.env`, data files or model files.
