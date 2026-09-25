# Knowledge transfer — KoylaSetu AI

Written for whoever picks this project up next. Read this before touching code.
Last updated: 2026-09-25, against `dev` at commit `4988b3d` (after PR #31).

## 1. What this is, in one paragraph

KoylaSetu AI helps CMPDI/Coal India answer Parliamentary Questions and produce
reports without staff manually digging through scanned PDFs and spreadsheets.
It reads documents, pulls out verified numbers with their exact source
(document + page), and gives three tools on top: Q&A with citations, one-click
report drafts, and topic/trend dashboards. Full spec:
[`docs/KoylaSetu_AI_Developer_Guide.docx`](KoylaSetu_AI_Developer_Guide.docx).

**The one rule that governs every design decision here:**
*Numbers come from the database, words come from the AI, and every figure has
a source.* The LLM is never allowed to invent a number — if it can't find a
verified figure, it says so.

## 2. Repo map

```
backend/app/
  api/          FastAPI routers — one file per resource (auth, documents, qa, reports, users, audit)
  core/         config.py (env vars), db.py (session), deps.py (auth + RBAC + org scoping), rbac.py, security.py
  models/       SQLAlchemy models — org.py, document.py, fact.py, report.py, enums.py, base.py
  schemas/      Pydantic request/response shapes, one file per resource
  services/     business logic used by api/ and worker/ (audit, qa, grounding, retrieval, storage, ...)
  llm/          the Ollama client + system prompts
  scripts/seed.py   creates org units + 6 demo users

backend/worker/  RQ background jobs, run by `rq worker ingest topics reports`
  ingest.py      orchestrates one document: OCR -> parse -> extract -> embed
  ocr.py         Tesseract (Paddle not built)
  parse.py       PDF/Excel/Word -> pages, text, tables
  embed.py       chunking + BGE-M3 embeddings
  extract.py     tables -> Fact rows, with source page/bbox
  validate.py    STUB — validation rules not built
  topics.py      STUB — word cloud / topic modeling not built

backend/alembic/versions/   2 migrations so far (0001_initial, 0002_table_cell_bboxes)

frontend/src/
  app/(app)/     every authenticated page — see section 5 for what exists
  app/login/     the one unauthenticated page
  components/AppShell.tsx   header, nav (built conditionally per permission), the useMe() hook
  lib/api.ts     the ONLY place that calls the backend — typed fetch wrappers
  lib/i18n.tsx   every UI string, English + Hindi, keyed by LabelKey — never inline strings in pages

docs/SETUP.md    Docker-first setup guide (works, but skips the non-Docker path's real complexity — see section 6)
scripts/setup_local.sh, scripts/setup_local_db.py   one-shot local (non-Docker) setup
data/sources.csv  100 real public files catalogued, 99 distinct (two PQ URLs serve the same file); download: scripts/fetch_sources.py, upload: scripts/load_sources.py — files themselves are git-ignored
eval/pq_benchmark.jsonl   34 real Lok Sabha coal PQs with official answers and key figures (format checked by scripts/check_benchmark.py)
```

## 3. Architecture at a glance

- **Backend**: FastAPI (Python 3.12+ fine despite `pyproject.toml` saying 3.11), SQLAlchemy 2.0, Alembic, Postgres 15/16 + pgvector, Redis + RQ for background jobs.
- **Frontend**: Next.js (App Router) + Tailwind, plain `fetch` wrapped in `lib/api.ts` (no React Query / SWR — deliberately simple).
- **Auth**: JWT access (30 min) + refresh (7 day) tokens, argon2 password hashing. Tokens live in `sessionStorage` (explicit TODO in code to move to httpOnly cookies before real deployment).
- **LLM**: Ollama, local-only by default (`ALLOW_EXTERNAL_CALLS=false`). `backend/app/llm/client.py` is the only thing that talks to it.
- **RBAC + org scoping**: every list/detail query in every router is wrapped in `scope_to_user()` (`app/core/deps.py`) — a user only sees their own org unit's rows, unless their unit is `CIL_HQ` or `MINISTRY` (see `ALL_SCOPE_ORG_CODES`), in which case they see everything. **Apply this on every new query** — it's not automatic, you have to call it. The audit
  log was missed exactly this way and shipped unscoped for a while (see §9); when you add a
  table that people will list, give it an `org_unit_id` at the same time as the model, not
  later.

## 4. Data model — the tables that matter

| Table | What it holds |
|---|---|
| `org_units`, `users` | 10 org units (8 subsidiaries + CIL_HQ + Ministry), users with a list of roles |
| `documents`, `pages`, `chunks`, `extracted_tables` | uploaded files, their pages, searchable text chunks (with embeddings + full-text), raw extracted table grids |
| `facts` | **the core table** — one verified number per row: metric, subsidiary, period, value, unit, and `document_id` + `page_no` + `bbox` as the source pointer |
| `validation_issues` | flags on a `Fact` from an automatic check (rules not built yet — table is ready, nothing writes to it) |
| `review_actions` | human accept/edit/reject decisions on a `Fact` (no UI for this yet — see open issue #6) |
| `reports`, `report_versions`, `report_citations` | the report workflow: current state + title in `reports`, full edit history in `report_versions`, every figure's source link in `report_citations` (not populated yet — no generator writes citations) |
| `parliament_questions` | past + new PQs; will be both the benchmark and the topic-model source once populated |
| `qa_logs`, `topics`, `audit_log` | every Q&A asked (with grounding result), topic-model output (nothing writes here yet), and the system-wide audit trail |

## 5. What's actually working right now (verified by hand, not just "code exists")

✅ **Auth & accounts** — login, JWT refresh, change-own-password, Admin can create/edit/deactivate users
✅ **Document upload** — type-sniffed, deduped by sha256, audit-logged, queues an ingest job
✅ **OCR + parsing** — Tesseract reads scanned pages; native-text PDFs skip OCR; Excel/CSV/Word all parse
✅ **Chunking + embeddings** — pages become searchable chunks (BGE-M3 + full-text)
✅ **Fact extraction** — tables become `Fact` rows with exact source page/bbox
✅ **Document viewer** — open a document, page through it, see the image with the cited passage highlighted
✅ **Q&A (text route only)** — ask a question in English/Hindi, get an answer grounded in retrieved chunks, with citations that link to source pages. **The numeric route (Text-to-SQL against `facts`) is NOT built** — every answer today comes from document text, never a direct database lookup, even though `facts` now has real data to query. This is the single most important gap relative to the project's core promise.
✅ **Reports workflow** — create/edit/submit/approve/return with full version history and required rejection comments. **No AI drafting** — an Analyst types the content by hand. This is the shell issue #8/#9's generators will plug into.
✅ **Admin, audit log, change-password screens**

## 6. What's partially built or stubbed

- `worker/validate.py` — 4 lines, docstring only. No automatic checks run on extracted facts.
- `worker/topics.py` — 1 line, docstring only.
- Q&A numeric/SQL route — see above.
- `data/` has 100 files (99 distinct) catalogued in `sources.csv`. The download script only populates local files; load them into a running instance with `scripts/load_sources.py` before assuming there's real content to query.
- `eval/pq_benchmark.jsonl` — 34 real PQs (see README "Benchmark set"). The runner is `eval/run_eval.py` (logic in `scripts/benchmark_runner.py`, PR #49).

## 7. Not started at all

- Validation rules (V01–V08 in the dev guide)
- Human review queue UI (approve/correct/reject a flagged fact)
- Report *generation* (PQ reply, monthly, briefing) — the AI drafting itself
- Topic modeling / word cloud
- Real home dashboard (`app/(app)/page.tsx` is still a labeled placeholder — read the comment in the file)
- Benchmark data + the eval run itself

## 8. Running it locally WITHOUT Docker (tested end-to-end this session)

`docs/SETUP.md` is Docker-first and glosses over the non-Docker path. Here's what actually works, on macOS:

1. **Postgres + pgvector**: if you already have Postgres via Homebrew, don't reinstall — just build pgvector from source against it:
   ```bash
   git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git /tmp/pgvector-build
   cd /tmp/pgvector-build
   PG_CONFIG=$(brew --prefix postgresql@15)/bin/pg_config make
   PG_CONFIG=$(brew --prefix postgresql@15)/bin/pg_config make install   # no sudo needed, Homebrew dirs are user-owned
   ```
   Then `createuser`/`createdb` as needed and `CREATE EXTENSION vector;` in the app database.

   ⚠️ **Do not `brew install pgvector`** on an old macOS (Monterey or older) — Homebrew has no precompiled bottle for it and will try to build LLVM and Rust from source as transitive dependencies, which can run for hours. Building pgvector directly against your existing Postgres (above) takes under a minute.

2. **Redis**: same reasoning — build from source instead of `brew install redis`:
   ```bash
   curl -fsSL https://download.redis.io/releases/redis-7.4.2.tar.gz | tar xz -C /tmp/redis-build --strip-components=1
   cd /tmp/redis-build && make -j4
   ./src/redis-server --daemonize yes --port 6379
   ```

3. **Backend**: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then `alembic upgrade head`, then `python -m app.scripts.seed`, then `uvicorn app.main:app --reload`.

4. **Worker**: `rq worker ingest topics reports` in a separate terminal.

   ⚠️ **macOS fork-safety crash**: the worker will crash with `objc[...]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was called` the moment it tries to process a job, because RQ forks a subprocess and something in the ingestion stack (Pillow/PaddleOCR-adjacent) has already touched the Objective-C runtime. Workaround: `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest topics reports`. This is an environment quirk, not a code bug — don't "fix" it in the pipeline code.

5. **Frontend**: `npm install && npm run dev`.

6. **LLM**: install Ollama, `ollama pull qwen2.5:3b-instruct` and `ollama pull bge-m3`, and set `LLM_BASE_URL=http://localhost:11434` in `.env` ([SETUP.md section 10](SETUP.md#10-local-ai-model-server-ollama-without-docker)). Then `cd backend && .venv/Scripts/python ../scripts/check_llm.py` confirms it answers. Without this, Q&A and embeddings silently no-op rather than erroring (check worker logs for "Embeddings skipped: model server not reachable").

**Most of the above is now scripted** (PR #34): `bash scripts/setup_local.sh --seed` does the
whole thing, and `scripts/setup_local_db.py` does the database half on any OS — see
`docs/SETUP.md` §"Local setup without Docker". The manual steps above are still worth
reading, because the script `brew install`s Postgres and Redis, which is the one thing you
must not do on Monterey or older. If you already have them, run `setup_local_db.py`
directly against your existing Postgres instead of the shell script.

## 9. Other gotchas worth knowing before you touch things

- **`backend/data/` vs `data/`**: if `STORAGE_DIR` in your `.env` is a relative path (e.g. `./data/files`) and you run the backend from inside `backend/`, uploaded files land in `backend/data/`, which is a *different, previously-ungitignored* path from the repo-root `data/` that's meant for `sources.csv`. This was a real gap (fixed in PR #28) — if you see it regress, check `.gitignore` still has the `backend/data/` line.
- **`useT()`'s `t` function is not memoized** — it's a new function reference on every render. Do **not** put `t` in a `useEffect` dependency array; it causes an infinite fetch loop (I found and fixed exactly this bug in the document detail page — see PR #27's description for the full story, even though that PR itself was later closed as superseded). If an effect needs a translated string for an error state, store an error *code*/*kind* in state and translate only at render time.
- **The page-image endpoints need the Authorization header**, so a plain `<img src="...">` can't hit them directly — use `fetchImageUrl()` from `lib/api.ts`, which fetches with auth and hands back a blob URL. Remember to `URL.revokeObjectURL()` on cleanup.
- **Approver has `edit_reports` too**, not just `approve_reports` (see the permission matrix in section 10) — an Approver can edit a report's content, not just approve/reject it. This is intentional, not a bug, per `app/core/rbac.py`.
- **`audit_log` rows carry their own `org_unit_id`**, stamped by `services/audit.py:record()`
  from the acting user — which is why `record()` takes the `User` and not just their id. A
  null unit (a system action, or a failed login on an unknown email) is visible only to CIL
  HQ / Ministry. If you add an audit call, pass `actor=`; don't reconstruct the row by hand.
- **`i18n.tsx` is a single shared file everyone edits** — when adding a new feature, check for key-name collisions with unrelated features before assuming your key is free (e.g. `createButton` collided between the admin-users and reports-screen work and had to be split into `createButton` / `createReportButton`). Grep the file before naming a new generic-sounding key like `save`, `cancel`, `edit`.
- **This repo has active parallel development.** Multiple people (including AI-assisted sessions) have been building simultaneously. Before starting new work: `git fetch && git log origin/dev --oneline -15` to see what's landed recently — more than once during this session, work that looked unclaimed turned out to already be in progress or freshly merged elsewhere (see PR #27 in the PR history: closed, not merged, because PR #30 had independently built the same screen, better integrated, while the other PR was in flight).

## 10. Roles & permissions (current matrix — `backend/app/core/rbac.py`)

| Permission | Admin | Operator | Reviewer | Analyst | Approver | Viewer |
|---|---|---|---|---|---|---|
| manage_admin (user mgmt) | ✅ | | | | | |
| upload_documents | ✅ | ✅ | ✅ | | | |
| view_processing | ✅ | ✅ | ✅ | ✅ | | |
| review_facts | ✅ | | ✅ | | | |
| ask_questions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| edit_reports | | | | ✅ | ✅ | |
| approve_reports | | | | | ✅ | |
| export_reports | ✅ | | | ✅ | ✅ | ✅ |
| view_topics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| view_audit | ✅ | | | | ✅ | |

6 demo accounts exist (all password = `SEED_DEMO_PASSWORD` from `.env`): `admin@`, `operator@`, `reviewer@`, `analyst@`, `approver@`, `viewer@koylasetu.local`.

## 11. Where to pick up next

Start at **[issue #12 — Roadmap](https://github.com/Deepak29-c/koylasetu-ai/issues/12)**, which lists every remaining piece of work in dependency order. As of this writing, roughly **40–45% of the full roadmap is done** — solid on the document pipeline and the screens built this session, but the two things closest to the project's actual pitch (numeric Q&A grounded in `facts`, and AI-generated report drafts) are not built. Highest-leverage next steps, in order:

1. **Q&A numeric route** — `facts` has real data now (PR #32); the router in `services/qa.py` still only does the textual route. This is the single biggest gap vs. the core promise.
2. **Validation rules** (`worker/validate.py`) — the safety net that makes "verified" mean something.
3. **Report generation** (issues #8/#9) — plug an AI draft into the workflow shell this session built (PR #31).
4. **Review queue UI** (issue #6) — the human half of the validation safety net.

## 12. Git workflow (already established, don't deviate)

`main` = demo-ready, `dev` = integration, feature branches like `feat/whatever`. Every PR targets `dev`, needs CI green (`ruff`/`black`/`pytest` backend, `eslint`/`next build` frontend — see `.github/workflows/ci.yml`), and per `docs/SETUP.md` is supposed to get one human review before merging. Never commit `.env`, uploaded documents, or model files.
