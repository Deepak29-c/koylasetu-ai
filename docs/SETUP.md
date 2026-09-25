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

## 10. Local AI model server (Ollama) without Docker

Every AI feature (answering questions, writing reports, search embeddings) calls a model server
on **this machine**. Nothing is sent to an outside AI company: `app/llm/client.py` refuses any
`LLM_BASE_URL` that is not this machine or the local network unless `ALLOW_EXTERNAL_CALLS=true`,
and that setting must stay `false`.

We need two models:

| Model | Setting | Used for | Download |
|---|---|---|---|
| `qwen2.5:3b-instruct` | `LLM_MODEL` | Writing answers and reports (laptops, CPU only) | ~1.9 GB |
| `qwen2.5:7b-instruct` | `LLM_MODEL` | Same, better answers (GPU or 16 GB+ RAM, demo machine) | ~4.7 GB |
| `bge-m3` | `EMBED_MODEL` | Search embeddings (1024 numbers per passage) | ~1.2 GB |

### Disk, memory and time

| | 3B + bge-m3 | 7B + bge-m3 |
|---|---|---|
| Disk | ~3 GB (plus ~1 GB for Ollama itself) | ~6 GB (plus ~1 GB) |
| Free RAM while answering (CPU) | ~4-5 GB | ~7-8 GB |
| Download at 50 Mbit/s | ~10 min | ~20 min |
| Answer to a question (CPU laptop) | ~30-60 s | ~2-3x slower without a GPU |

Models are stored in `~/.ollama/models` (Windows: `C:\Users\<you>\.ollama\models`). Set the
`OLLAMA_MODELS` environment variable before starting Ollama to keep them on another drive.
The first question after starting takes longer: the model is loaded into memory then, and
unloaded again after 5 idle minutes.

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
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:3b-instruct         # must match a model in `ollama list`
EMBED_MODEL=bge-m3
ALLOW_EXTERNAL_CALLS=false
```

`.env.example` has `LLM_BASE_URL=http://ollama:11434`, which is the Docker service name and
only works inside Docker Compose; change it to `localhost` when Ollama runs natively.

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
| Download stops or is very slow | Run `ollama pull` again: it resumes where it stopped |
| Pulled models filled drive C: | Set `OLLAMA_MODELS` to a folder on another drive, restart Ollama, pull again |
