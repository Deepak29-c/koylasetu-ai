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

Not built yet: tables → facts + validation + review queue (step 3), Q&A (step 2), reports,
topics, and the benchmark. PaddleOCR (`OCR_ENGINE=paddle`) currently falls back to Tesseract.

## Run with Docker (the normal way)

```bash
cp .env.example .env          # then change JWT_SECRET and SEED_DEMO_PASSWORD
docker compose up -d --build db redis api worker web
docker exec koyla-api python -m app.scripts.seed
```

When we reach the Q&A step, also start the local AI model server and pull the models
(multi-GB download):

```bash
docker compose up -d ollama
docker exec ollama ollama pull qwen2.5:7b-instruct
docker exec ollama ollama pull bge-m3
```

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

## Checks

```bash
cd backend && ruff check . && black --check . && pytest -q
cd frontend && npm run lint && npm run build
```

## Git workflow

`main` = demo-ready, `dev` = integration, feature branches like `feat/qa-grounding`.
Every change goes through a PR with one reviewer. Never commit `.env`, data files or model files.
