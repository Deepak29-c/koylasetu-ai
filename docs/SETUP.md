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
