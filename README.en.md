# AICodingProjectAssistance

[中文](README.md) | **English**

> **Note**: the web UI and the [operation handbook](docs/系统操作手册.md) are currently **Chinese-only**. This English README tells you what the project is and how to install, configure and deploy it.

A platform for end-to-end assistance and project management of AI coding projects. It covers **requirement analysis → project planning → architecture design → task management → worklog → testing → delivery documents → operations**, plus a knowledge base, an LLM-compiled Wiki, model configuration, RBAC and an MCP server.

**Lightweight**: the whole flow runs on a single machine. Business data lives in SQLite and the vector store is embedded Chroma — both are local files, so there is no database server or vector service to run. The backend needs only 13–14 Python packages and no torch when using remote embeddings. The MCP server is a single file speaking pure stdio (listing its tools needs nothing but the standard library). Deployment is 2 containers and 1 data volume.

---

## Features

- **Full lifecycle**: requirement → planning → architecture → development → delivery → operations, with precondition checks between stages and automatic stage transitions.
- **AI generation**: requirement completeness review, project plan generation with weighted task breakdown, two-step streaming generation of the architecture document and its DDL, test cases generated from requirements or tasks, weekly summaries.
- **Two knowledge systems**: a knowledge base (classic RAG, good at exact source text) and a Wiki (LLM compiles source documents into structured pages, good at global understanding and backlink navigation).
- **Human–agent collaboration**: the work group acts as a message bus between people and agents (agents report progress, claim tasks); worklogs and member profiles assist dispatch.
- **MCP server**: lets coding agents such as Trae / Claude Code / Cursor read and write platform data directly, with identity as permission.
- **Permissions**: whitelist-based RBAC (menu codes linked to API codes) with data isolation per project.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python + Django + DRF + SQLite + Chroma (vector store) |
| Frontend | Vue3 + Vite + Element Plus + Pinia |
| AI | LLM (OpenAI-compatible, e.g. DeepSeek) + Embedding (local bge-small-zh or remote) |

## Project Structure

```text
AICodingProjectAssistance/
├── backend/                    # Django backend
│   ├── config/                 # settings / urls
│   ├── apps/                   # accounts projects requirements knowledge collaboration
│   │                           # testing delivery ai_config project_planning architecture wiki rbac operation
│   ├── services/               # llm / embedding / vector_store / document_parser / ai_config / vision
│   ├── db.sqlite3              # business database (created by migrate, gitignored)
│   ├── chroma/ media/          # vector store and uploads (runtime, gitignored)
│   └── requirements.txt
├── frontend/                   # Vue3 frontend
├── mcp-client/                 # MCP server (single file, pure stdio)
│   ├── mcp_server.py
│   └── mcp_server_config.example.json   # config template (copy to mcp_server_config.json)
├── deploy/                     # Docker compose, Dockerfiles, nginx, data packaging script
└── docs/系统操作手册.md         # page-by-page and MCP handbook (Chinese)
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser        # create an admin account

# Optional: generate synthetic demo data (demo accounts + a full project)
python manage.py seed_demo
```

> To see what the system looks like, run `python manage.py seed_demo`. It creates a demo project and demo accounts (password `demo12345` for all, e.g. `demo_manager`, `demo_dev1`, `demo_tester`). All data is generated in code and contains no real personal information. To wipe and recreate: `python manage.py seed_demo --reset`.

### 2. Frontend

```bash
cd frontend
npm install
```

### 3. Run

```bash
# Terminal 1: backend
cd backend
python -u manage.py runserver 127.0.0.1:8000

# Terminal 2: frontend
cd frontend
npm run dev
```

Open http://127.0.0.1:5173/ — `/api` and `/media` are proxied to port 8000.

> There is **no self-service sign-up**. Accounts are created by an administrator under "User Management", or via `createsuperuser`.

## Configuration

### LLM / Embedding

Settings in the "Model Config" page take precedence; environment variables are the fallback.

```bash
export LLM_API_KEY="sk-xxx"
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"
# Remote embedding: export EMBEDDING_MODE="remote"; export LLM_EMBEDDING_MODEL="nomic-embed-text"
```

> On Windows PowerShell the syntax is `$env:LLM_API_KEY="sk-xxx"` instead of `export`.

To download the local embedding model (default `BAAI/bge-small-zh-v1.5`), pick one:

```bash
# Option 1: HuggingFace mirror (restart the backend afterwards; the first "Test Embedding" downloads and caches it)
export HF_ENDPOINT="https://hf-mirror.com"

# Option 2: ModelScope offline download (most reliable from mainland China)
python -m pip install modelscope
python -c "from modelscope import snapshot_download; print(snapshot_download('BAAI/bge-small-zh-v1.5', cache_dir='<your-model-dir>'))"
```

ModelScope creates a `.../snapshots/master/` directory (where the real model files live); the level above it is only a cache index. In "Model Config" you must point the local model name at **the level that contains `config.json` / `model.safetensors` / `tokenizer.json`**.

### Service Token (for MCP and other agents to call the API without logging in)

```bash
export PLATFORM_SERVICE_TOKEN="your-own-token"
```

Send `Authorization: Bearer <token>` to access all endpoints. The token maps to an automatically created administrator account named `mcp`, so **use it only on localhost or in a trusted environment**.

> With `DEBUG=0` (production mode), the backend refuses to start if the default token or default secret key is still in use, forcing you to set your own values.

## MCP Server

The server is a single file speaking pure stdio (listing its tools needs nothing but the standard library; `httpx` is required only for actual API calls).

```bash
pip install httpx
```

Copy the config template and fill it in (the real config file is gitignored):

```bash
cp mcp-client/mcp_server_config.example.json mcp-client/mcp_server_config.json
```

```json
{
  "PLATFORM_API_URL": "http://127.0.0.1:8000",
  "PLATFORM_API_TOKEN": "mcp-xxxxxxxxxxxxxxxx",
  "PLATFORM_PROJECT_ID": "1"
}
```

Register the stdio MCP server in Cursor / Claude Code / VS Code / Trae (`PLATFORM_API_TOKEN` should be the **MCP Token** of a user, found under "User Management"; it starts with `mcp-`):

```json
{
  "mcpServers": {
    "ai-platform": {
      "command": "python",
      "args": ["./mcp-client/mcp_server.py"]
    }
  }
}
```

There are 55 tools covering the knowledge base / Wiki, requirements / planning, architecture / SQL, tasks / worklogs / group messages, testing / bugs, operations, prototype images / member profiles and delivery documents. Frequently used ones include `knowledge_search`, `requirement_content_query`, `architecture_query`, `task_query`, `task_update` and `worklog_submit`; the full list is in chapter 4 of the [operation handbook](docs/系统操作手册.md) (Chinese).

## Docker Deployment (Linux)

Two services: `backend` (Django + gunicorn) and `frontend` (nginx serving the built frontend and reverse-proxying the API). Runtime data lives in the `deploy/data/` volume.

```bash
# Server prerequisites
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

```powershell
# On Windows: package the current data (database / vector store / uploads) into deploy/data_initial/
cd AICodingProjectAssistance
powershell -ExecutionPolicy Bypass -File deploy\prepare_data.ps1
```

Upload the whole directory to the server (**make sure `deploy/data_initial/` is included**), then:

```bash
cd AICodingProjectAssistance/deploy
docker compose up -d --build
```

Open `http://<server-ip>/`. The first build pulls images and installs dependencies, so a few minutes (up to ~15) is normal.

### Required Before Going Live

Write these into `deploy/.env` or export them:

| Variable | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | **Required.** If unset, compose exits with an error — this prevents shipping the development default. Generate with: `python deploy/gen_secret.py` |
| `PLATFORM_SERVICE_TOKEN` | **Required.** The default maps to the administrator account `mcp`; with `DEBUG=0` the backend refuses to start while it is unchanged |
| `DJANGO_ALLOWED_HOSTS` | Defaults to `*`; set it to your server IP or domain |

### Two Deployment Modes

Both use the same data volume, so **pick one and stay with it** — mixing them makes the vector store and the embedding model inconsistent:

- **Lightweight remote mode (default)**: no torch installed; the container calls a remote OpenAI-compatible embedding endpoint (`EMBEDDING_MODE=remote`). Smaller image, faster build.
- **Bundled local mode**: the image ships bge-small-zh and works offline, at the cost of downloading torch (~500 MB+) on the first build.

```bash
# Switch to bundled local mode
export INSTALL_LOCAL_EMBEDDING=true
export EMBEDDING_MODE=local
docker compose up -d --build
```

pip defaults to the Tsinghua mirror and the model to hf-mirror.com (works out of the box in mainland China). On an overseas server, switch to the official sources — and **build first, then start** (do not pass `--build`, or these arguments are not applied):

```bash
docker compose build --build-arg PIP_INDEX_URL=https://pypi.org/simple --build-arg HF_ENDPOINT=https://huggingface.co
docker compose up -d
```

### Notes

- On first start the database contains schema only. For demo data, run on the server:
  `docker compose exec backend python manage.py seed_demo` (add `--reset` to recreate).
- `deploy/data_initial/` is packaged from your machine by `prepare_data.ps1` and contains the database and uploads (possibly including API keys and business data). It is excluded by `.gitignore` — **never commit or publish it**.
- **Updating data**: after re-packaging, delete `deploy/data/` (or the relevant entries) before `docker compose up -d`, otherwise the new initial data is not applied.
- Useful commands: `docker compose logs -f backend`, `docker compose down`, `docker compose up -d --build`.
- If the site is unreachable, check that port 80 is open in the firewall (e.g. `ufw allow 80/tcp`) or change the port mapping in `docker-compose.yml`.

## Project Lifecycle

```text
Requirement analysis → Project planning → Architecture design → Development → Delivery → Operations
```

- **Requirement analysis**: upload a requirement document → AI completeness review → confirm to store
- **Project planning**: pick members and development weights → AI generates a plan → generate and assign tasks
- **Architecture design**: pick tech stack / base framework / database → two-step streaming generation of the architecture document and DDL
- **Task management**: view, add, edit, change status; worklogs link to tasks; export to Excel

## Two Knowledge Systems

|  | Knowledge Base | Wiki |
|---|---|---|
| Mechanism | Classic RAG: chunking + vector search | LLM compiles source documents into structured pages first, then searches them |
| Strength | **Exact source text**: how a clause is worded, precise values | **Global understanding**: how it is designed, why, how modules relate |
| Weakness | Chunk noise; cannot answer cross-module questions | Compilation loses original wording and detail |
| Storage | Chroma collection `project_{id}` | SQLite + a separate collection `wiki_{project_id}` (physically isolated) |

Q&A behaviour: the knowledge base does a single top-k vector search; the Wiki is agentic and multi-turn (hit pages first, then follow backlinks to fill gaps, up to 3 extra pages). After source documents change, the Wiki can be **recompiled in place**, so there is no mix of stale and fresh chunks.

## Main APIs

| Module | Endpoints |
|---|---|
| Auth | `/api/auth/login/` `/refresh/` `/me/` `/change-password/` `/admin-users/` |
| Projects | `/api/projects/` `/members/invite/` `/members/{uid}/` |
| Requirements | `/api/requirements/upload/` `/{id}/analyze/` `/{id}/confirm/` |
| Knowledge base | `/api/knowledge/add/` `/search/` |
| Planning | `/api/project-plans/generate/` `/{id}/regenerate/` `/{id}/generate-tasks/` |
| Tasks | `/api/plan-tasks/` |
| Architecture | `/api/architecture/generate-stream/` `/{id}/chat-stream/` `/{id}/chat/` |
| Worklog / weekly | `/api/work-logs/` (incl. `/statistics/`, `/export/`), `/api/weekly-summaries/` |
| Testing | `/api/test-cases/` `/api/test-tasks/dispatch/` |
| Delivery | `/api/delivery-docs/` `/upload/` |
| Model config | `/api/ai-config/` `/api/ai-config/test/` |

## FAQ

| Problem | Fix |
|---|---|
| Service token returns 401 | Make sure the backend was restarted (the service token authenticator now runs first) |
| Local embedding times out | Usually HuggingFace is unreachable; set `HF_ENDPOINT=https://hf-mirror.com` or use ModelScope |
| AI generation feels slow | Request timeouts are already generous; increase `proxyTimeout` for `/api` in `frontend/vite.config.js` if needed |
| After adding an app | Run `python manage.py makemigrations && python manage.py migrate` |
| Menus missing / API returns 403 | The resource code for that feature is not granted to your permission group; enable it under "Permission Groups" |

For page-by-page and MCP usage details, see the **[operation handbook](docs/系统操作手册.md)** (Chinese).
