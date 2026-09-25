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

   The background worker (RQ) needs `fork`, which Windows does not have: run
   `rq worker ingest topics reports` inside WSL, or use Docker for the worker only.

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
.venv/bin/rq worker ingest topics reports           # another terminal (WSL on Windows)
cd ../frontend && npm install && npm run dev        # another terminal
```

For Q&A, install Ollama from https://ollama.com and pull the models:
`ollama pull bge-m3` and `ollama pull qwen2.5:3b-instruct`.

| Problem | Fix |
|---|---|
| `pgvector is not installed in this Postgres` | Install it for the **same** Postgres version the server runs (see above) |
| `Cannot connect to Postgres as admin` | Start Postgres; pass `--admin-url` with a superuser and its password |
| `password authentication failed for user "koyla"` | Re-run the script: it resets the role's password to the one in `.env` |
| Port 5432 already used by another Postgres | Point `DATABASE_URL` and `--admin-url` at that server, or stop it |
