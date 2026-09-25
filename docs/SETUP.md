# Local setup guide

Everything a team member needs to run KoylaSetu AI on their own machine.

## 1. Hardware

| | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB (the AI model needs it later) |
| Free disk | 20 GB | 30+ GB (Docker images + ~5 GB AI model) |
| CPU | Any 64-bit with **virtualization enabled** | 8+ cores |
| GPU | Not needed | NVIDIA with 6–8 GB VRAM, makes the AI model fast (from build step 2) |
| OS | Windows 10/11, macOS or Linux | – |

Check virtualization on Windows: Task Manager → Performance → CPU → **"Virtualization: Enabled"**.
If it says Disabled, turn it on in the BIOS (called Intel VT-x or AMD SVM).

## 2. Accounts

- A GitHub account. The repo is private, so ask Deepak (Deepak29-c) to add you as a collaborator.

## 3. Software

### Required

| Tool | Why | Get it |
|---|---|---|
| Git | Download the code | https://git-scm.com |
| WSL 2 (Windows only) | Docker needs it | Admin PowerShell: `wsl --install`, then restart |
| Docker Desktop | Runs database, Redis, API, worker and website | https://www.docker.com/products/docker-desktop (keep "Use WSL 2" ticked) |

### Optional (tests or coding outside Docker)

| Tool | Why |
|---|---|
| Python 3.11 | Run backend tests (3.11 matches the Docker image) |
| Node.js 20 | Run the website with `npm run dev` |
| VS Code | Editor (Python, ESLint and Docker extensions) |
| GitHub CLI (`gh`) | Pull requests from the terminal |

## 4. First-time setup

1. Clone the repo:

   ```bash
   git clone https://github.com/Deepak29-c/koylasetu-ai.git
   cd koylasetu-ai
   ```

2. Create your `.env`:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:
   - `JWT_SECRET=` any random text, 32+ characters
   - `SEED_DEMO_PASSWORD=` the password for the demo logins

   Everyone makes their own `.env`. Never commit it or share it.

3. Open Docker Desktop and wait until it shows **"Engine running"**.

4. Build and start (first time takes 5–10 minutes):

   ```bash
   docker compose up -d --build
   ```

   The first time this also downloads the Ollama image (the local AI model server, a few GB).

   Then download the two AI models once (about 3 GB in total):

   ```bash
   docker exec ollama ollama pull bge-m3
   docker exec ollama ollama pull qwen2.5:3b-instruct
   ```

   The 3B model is for laptops without a GPU. On a machine with a GPU or 16 GB+ RAM for Docker,
   pull `qwen2.5:7b-instruct` and set `LLM_MODEL=qwen2.5:7b-instruct` in `.env`.

5. Create the demo users:

   ```bash
   docker exec koyla-api python -m app.scripts.seed
   ```

6. Open http://localhost:3000 and log in.

### Demo logins

All use the password you set in `SEED_DEMO_PASSWORD`.

| Email | Role | Unit |
|---|---|---|
| admin@koylasetu.local | Admin | CIL HQ |
| operator@koylasetu.local | Data Operator | CMPDI |
| reviewer@koylasetu.local | Reviewer | CMPDI |
| analyst@koylasetu.local | Analyst | CIL HQ |
| approver@koylasetu.local | Approver | CIL HQ |
| viewer@koylasetu.local | Viewer | Ministry |

## 5. Check that it works

| Check | Expected |
|---|---|
| `docker compose ps` | 6 containers "running" (db, redis, ollama, api, worker, web) |
| http://localhost:8000/health | `{"status":"ok"}` |
| http://localhost:8000/docs | API documentation page |
| Upload a PDF as operator | "Uploaded", then Processing → **Processed** on Documents |
| Ask a question about that PDF on the Ask page | An answer with source chips; clicking one opens the page highlighted (30-60 s on a laptop CPU) |

## 6. Daily commands

| What | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| After pulling new code | `docker compose up -d --build` |
| See API errors | `docker compose logs -f api` (or `worker`, `web`) |
| Wipe the database and start fresh | `docker compose down -v`, then start and seed again |
| Backend tests (needs Python 3.11) | `cd backend`, create a venv, `pip install -r requirements.txt`, `pytest -q` |

## 7. Common problems

| Problem | Fix |
|---|---|
| `docker: command not found` right after installing | Close and reopen the terminal |
| `failed to connect to the docker API … docker_engine` | Docker Desktop is not running. Open it and wait for "Engine running" |
| Error about the `docker-users` group | Sign out of Windows and sign back in |
| Build fails with `rpc error … EOF` | Build one at a time: `docker compose build api`, then `docker compose build web`, then start |
| First start downloads many GB | Expected once: the Ollama image and the two models. Later starts reuse them |
| Ask page says "The local AI model is not available" | `docker compose up -d ollama`, and check `docker exec ollama ollama list` shows both models |
| Answers are very slow | Normal on CPU (30-60 s with the 3B model). Close other heavy apps; a GPU machine is much faster |
| "An Application Control policy has blocked this file" (Python outside Docker) | Windows Smart App Control blocks SQLAlchemy's compiled files. See the Windows note in the README |
| Port 3000, 8000 or 5432 already in use | Stop the other app using that port (e.g. a local Postgres or another Next.js project) |
| Login says "Wrong email or password" | Use the `SEED_DEMO_PASSWORD` from your own `.env`, and make sure you ran the seed step |

## 8. Git workflow

- `main` = demo-ready, `dev` = integration.
- Create a feature branch from `dev`, e.g. `git switch dev && git pull && git switch -c feat/my-change`.
- Open a pull request into `dev`, get one review, CI must pass.
- Never commit `.env`, data files or model files.

## 9. Run without Docker

For machines where Docker is not wanted. You need three things running locally: PostgreSQL 16
**with the pgvector extension**, Redis, and (for Q&A) Ollama. The one step people get stuck on
is pgvector: it is a C extension, not a `pip install`, so it must match your Postgres build.

### macOS and Ubuntu / Debian: one script

```bash
bash scripts/setup_local.sh --seed
```

It installs Postgres 16 and Redis (Homebrew or apt), gets pgvector (the apt package, or
compiles it for Homebrew's Postgres), starts both services, creates `backend/.venv`, and then
runs `scripts/setup_local_db.py`. Everything is safe to run again.

### Windows

1. **PostgreSQL 16**: the EDB installer from https://www.postgresql.org/download/windows/.
   Remember the `postgres` password you choose.
2. **pgvector**: needs "Desktop development with C++" from Visual Studio Build Tools. In the
   **x64 Native Tools Command Prompt**, run as Administrator:

   ```bat
   set "PGROOT=C:\Program Files\PostgreSQL\16"
   git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
   cd pgvector
   nmake /F Makefile.win
   nmake /F Makefile.win install
   ```
3. **Redis**: Redis has no native Windows build. Use Memurai Developer (Redis-compatible,
   https://www.memurai.com) or run `sudo apt install redis-server` inside WSL.
4. **Database, migrations, demo users** (from the repo root, after creating `backend\.venv`
   with `pip install -r requirements.txt`):

   ```bat
   backend\.venv\Scripts\python scripts\setup_local_db.py --admin-url postgresql://postgres:YOUR_PASSWORD@localhost:5432/postgres --seed
   ```

   This gives you the API and the website on Windows. The background worker (RQ) does not
   run on native Windows (it needs `fork`), so `.env` has `INGEST_INLINE=true` (the setup
   script sets it on Windows): the API then processes each upload itself, one at a time, with
   the same code the worker runs. No Redis is needed. For heavy use, run the full stack in
   Docker or the backend in WSL 2 instead.

### What `scripts/setup_local_db.py` does (any OS)

Each step is skipped when it is already done, so run it again after pulling new code:

| Step | Details |
|---|---|
| `.env` | Created from `.env.example` with `localhost` hosts and a random `JWT_SECRET`, only if there is no `.env` yet |
| Role + database | From `DATABASE_URL` (default `koyla` / `koyla` / `koyla`); the role's password is kept in sync with `.env` |
| pgvector | `CREATE EXTENSION IF NOT EXISTS vector`; if pgvector is missing it stops and says how to install it |
| Migrations | `alembic upgrade head` |
| Demo users | With `--seed` |
| Redis | Checks that it answers; uploads stay "Uploaded" until it does |

The superuser connection comes from `--admin-url`, or `PG_ADMIN_URL`, or
`postgresql://postgres@localhost:5432/postgres`.

### Start the app

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload             # Windows: .venv\Scripts\uvicorn
.venv/bin/rq worker ingest topics reports           # another terminal (macOS / Linux)
cd ../frontend && npm install && npm run dev        # another terminal
```

For Q&A, install Ollama and pull the two models: see
[section 10](#10-local-ai-model-server-ollama-without-docker).

| Problem | Fix |
|---|---|
| `pgvector is not installed in this Postgres` | Install it for the **same** Postgres version the server runs (see above) |
| `Cannot connect to Postgres as admin` | Start Postgres; pass `--admin-url` with a superuser and its password |
| `password authentication failed for user "koyla"` | Re-run the script: it resets the role's password to the one in `.env` |
| Port 5432 already used by another Postgres | The script says which version answered. Stop the other server, or point `DATABASE_URL` and `--admin-url` at the right port (`pg_lsclusters` on Debian / Ubuntu) |
| `.env still points at Docker hosts` | Your `.env` came from the Docker setup: re-run with `--fix-env` to switch just those lines to `localhost` |

## 10. Local AI model server (Ollama) without Docker

Every AI feature (answering questions, writing reports, search embeddings) calls a model server
on **this machine**. Nothing is sent to an outside AI company: `app/llm/client.py` refuses any
`LLM_BASE_URL` that is not this machine or the local network unless `ALLOW_EXTERNAL_CALLS=true`,
and that setting must stay `false`.

**`ALLOW_EXTERNAL_CALLS`** is the only switch that lets the app send text to a model server
outside this machine / local network. It is `false` in the code default and in `.env.example`.
Never set it to `true` on a machine with real documents; `scripts/check_llm.py` fails while it is.

We need two models:

| Model | Setting | Used for | Download |
|---|---|---|---|
| `qwen2.5:3b-instruct` | `LLM_MODEL` | Writing answers and reports (laptops, CPU only) | ~1.9 GB |
| `qwen2.5:7b-instruct` | `LLM_MODEL` | Same, better answers (GPU or 16 GB+ RAM, demo machine) | ~4.7 GB |
| `bge-m3` | `EMBED_MODEL` | Search embeddings (1024 numbers per passage) | ~1.2 GB |

### Disk, memory and time

| | 3B + bge-m3 | 7B + bge-m3 |
|---|---|---|
| Disk (models) | 3.1 GB (`ollama list`: 1.9 GB + 1.2 GB) | ~5.9 GB (4.7 GB + 1.2 GB) |
| Disk (Ollama program) | ~1-2 GB (includes GPU libraries) | same |
| Memory while loaded, `LLM_NUM_CTX=8192` | 2.3 GB + 0.7 GB (`ollama ps`) | ~5.5 GB + 0.7 GB |
| RAM to have in the machine | 8 GB works, 16 GB comfortable | 16 GB, or a GPU with 8 GB |
| Download time | 2 min 46 s + 4 min 28 s here (~7 MB/s) | ~12 min at the same speed |
| Answer to a question | ~10 s on a laptop GPU (RTX 3050), ~30-60 s CPU only | GPU: ~2x the 3B time; CPU only: too slow, use 3B |

Measured on a Windows 11 laptop (i7-12650H, 16 GB RAM, RTX 3050 Laptop GPU, Ollama 0.34.4);
the 7B figures are estimates, it was not pulled here.

Models are stored in `~/.ollama/models` (Windows: `C:\Users\<you>\.ollama\models`). Set the
`OLLAMA_MODELS` environment variable before starting Ollama to keep them on another drive.
The first call after starting takes longer: the model is loaded into memory then (here 31 s
for `bge-m3`, 56 s for the 3B model the very first time, ~2 s after that), and unloaded again
after 5 idle minutes.

### Install

| OS | Install | Start the server |
|---|---|---|
| macOS | Download from https://ollama.com/download, or `brew install ollama` | Open the Ollama app (menu bar icon), or `ollama serve` (Homebrew: `brew services start ollama`) |
| Windows 10/11 | Installer from https://ollama.com/download, or `winget install Ollama.Ollama` | Starts by itself after install and at login (tray icon); otherwise `ollama serve` |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` | Installed as a systemd service: `sudo systemctl start ollama` |

An NVIDIA GPU (or Apple Silicon) is used automatically when present; nothing to configure.

### Download the models (once)

```bash
ollama pull bge-m3
ollama pull qwen2.5:3b-instruct       # or qwen2.5:7b-instruct on a GPU / 16 GB+ machine
ollama list                           # both should be listed
```

### Point the app at it

In your `.env` (repo root or `backend/`):

```
LLM_BASE_URL=http://127.0.0.1:11434   # localhost also works; see the Windows note below
LLM_MODEL=qwen2.5:3b-instruct         # must match a model in `ollama list`
EMBED_MODEL=bge-m3
ALLOW_EXTERNAL_CALLS=false
```

`.env.example` has `LLM_BASE_URL=http://ollama:11434`, which is the Docker service name and
only works inside Docker Compose; change it to `localhost` when Ollama runs natively
(`scripts/setup_local_db.py` from section 9 already does this when it creates your `.env`).
Without any `.env` the code defaults are the same as the block above (with `localhost`).

**Windows note:** Ollama listens on `127.0.0.1` only, and on Windows `localhost` is tried as
IPv6 (`::1`) first, which costs about 2 s on **every** call. Measured with
`scripts/check_llm.py`: server check 4.5 s with `localhost` vs 0.4 s with `127.0.0.1`, a
warm embedding 2.3 s vs 0.3 s, a warm chat 2.7 s vs 0.7 s. Use `http://127.0.0.1:11434`.

### Check it

```bash
cd backend
.venv/Scripts/python ../scripts/check_llm.py      # Linux/macOS: .venv/bin/python
```

It checks that the server is local and `ALLOW_EXTERNAL_CALLS=false`, that the server answers,
that both models are pulled (printing the `ollama pull` command for any missing one), that an
embedding has 1024 numbers, and that a tiny question gets an answer, with timings. It ends
with `Ready: questions can be answered by the local model.` and exit code 0.

If documents were uploaded before `bge-m3` was pulled, fill in their embeddings once:
`.venv/Scripts/python -c "from worker.embed import embed_missing; print(embed_missing())"`

### Problems

| Problem | Fix |
|---|---|
| `[FAIL] 2. server: no answer from http://localhost:11434` | Ollama is not running: open the Ollama app, or `ollama serve` (Linux: `sudo systemctl start ollama`) |
| `no answer from http://ollama:11434` | `ollama` is the Docker service name. Set `LLM_BASE_URL=http://localhost:11434` in `.env` |
| `[FAIL] 1. local-only: ... is not this machine or the local network` | `LLM_BASE_URL` points outside. Use `http://localhost:11434`; do not set `ALLOW_EXTERNAL_CALLS=true` |
| `[FAIL] 3. models: missing ...` | Run the `ollama pull` command it prints; the name must match `ollama list` exactly |
| `model server error 404 ... not found` in the app | `LLM_MODEL` / `EMBED_MODEL` in `.env` differ from what was pulled (e.g. 7b set, 3b pulled) |
| `expected 1 vectors of size 1024` | `EMBED_MODEL` is not `bge-m3`; the database column is 1024 wide, so use `bge-m3` |
| `address already in use` / `Only one usage of each socket address` on `ollama serve` | Ollama is already running (app or service), or the Docker `ollama` container holds port 11434: stop one of them |
| `model requires more system memory` | Close other apps, use the 3B model, or lower `LLM_NUM_CTX` to 4096 |
| First answer takes minutes | The model is loading into memory; later answers are faster. On CPU the 7B model is slow; use 3B |
| Every call takes ~2 s longer than it should (Windows) | Use `LLM_BASE_URL=http://127.0.0.1:11434` instead of `localhost` (see the Windows note) |
| Download stops or is very slow | Run `ollama pull` again: it resumes where it stopped |
| `ollama pull` fails with `lookup ... no such host` | A DNS / network blip (it happened once here): run the same `ollama pull` again |
| Pulled models filled drive C: | Set `OLLAMA_MODELS` to a folder on another drive, restart Ollama, pull again |
