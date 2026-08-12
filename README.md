# GitPilot — an AI agent that understands any GitHub repo

Paste any GitHub URL → GitPilot clones it, maps the codebase, and lets you **chat with the code** — every answer comes with file + line citations. Ask for a change and the agent **writes the code, runs the test suite in a sandbox, and opens a pull request**.

---

## 🔑 Where do the API keys go? (the ONLY change you need to make)

**One file: `.env`.** No `.py` file ever needs editing.

```bash
cp .env.example .env      # create your private config file
```

Now open `.env` and fill in:

| Key | Required? | Where to get it | What it unlocks |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ **yes** | platform.openai.com → API keys → "Create new secret key" | embeddings + answers + the agent |
| `GITHUB_TOKEN` | optional | GitHub → Settings → Developer settings → Personal access tokens (classic) → scope **`repo`** | the "open a pull request" feature |
| `REDIS_URL` | optional | e.g. `redis://localhost:6379` | shared cache (empty = built-in in-memory cache) |
| `CHAT_MODEL` / `EMBEDDING_MODEL` | optional | defaults: `gpt-4o-mini` / `text-embedding-3-small` | cost/quality tuning |

How it works: `gitpilot/config.py` is the **only** module that reads these values (via `os.getenv`). Everything else imports from there. That's why you never touch code to add keys — and why `.env` is listed in `.gitignore` so you can never leak them.

---

## Quickstart (5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add your OPENAI_API_KEY (see above)
python run.py                                         # → http://localhost:8000/docs
```

Run the tests:

```bash
pytest -q
```

---

## Demo script (interview-ready, ~4 minutes)

1. **Index a repo** — `POST /repos/index`
   ```json
   { "repo_url": "https://github.com/psf/requests" }
   ```
   → `{ "repo_id": "psf/requests", "files_indexed": ..., "chunks_indexed": ... }`

2. **Ask about the code** — `POST /ask`
   ```json
   { "repo_id": "psf/requests", "question": "How does this library handle redirects?" }
   ```
   → a grounded answer with citations like `requests/sessions.py (lines 120-145)`.

3. **Ask the same question again** → returns instantly with `"cached": true` — your caching story, live.

4. **Let the agent change code** — `POST /changes`
   ```json
   { "repo_id": "psf/requests",
     "instruction": "Add a module-level docstring to api.py summarizing the public functions",
     "open_pr": false }
   ```
   → watch the logs: the agent searches the code, reads files, writes the change, runs pytest in the sandbox, and summarizes.

5. **Open a real PR** — add `GITHUB_TOKEN` to `.env`, then the same call with `"open_pr": true` → the response contains a real `pull_request_url`.

> Tip: for the wow-factor demo, index the interviewer's own public repo and ask it questions live.

---

## Architecture

```
                 ┌──────────────────────── FastAPI app ─────────────────────────┐
                 │                                                              │
  POST /repos/index ──▶ repo_loader ──▶ chunker ──▶ OpenAI embeddings ──▶ Chroma │
                 │        (git clone)   (line-based,                     (vector │
                 │                       with citations)                  index) │
  POST /ask ─────────▶ cache? ──miss──▶ search Chroma ──▶ GPT answer + citations  │
                 │        │hit                                    │              │
                 │        └── return instantly ◀── store ◀────────┘              │
  POST /changes ──────▶ agent loop (ReAct):                                       │
                 │      search_code → read_file → write_file → run_tests         │
                 │      → (optionally) open_pull_request via GitHub API           │
                 │                                                              │
                 │  SQLite: repo metadata · Redis or in-memory: answer cache     │
                 └──────────────────────────────────────────────────────────────┘
```

| Piece | Choice | Why |
|---|---|---|
| API | FastAPI (async, `asyncio.to_thread` for blocking work) | never block the event loop |
| Vector DB | Chroma (persistent, cosine) | zero-setup embedded store; FAISS/Milvus swap is one module |
| Metadata | SQLite | file-based for the demo; swap `db.py` for PostgreSQL in prod |
| Cache | Redis or in-memory fallback | cache-aside pattern with TTLs |
| Agent | OpenAI function calling, max 12 steps | bounded loops, every action logged |
| Sandbox | subprocess, `shell=False`, pytest only, hard timeout | least privilege — no arbitrary LLM commands |

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + whether the OpenAI key is configured |
| POST | `/repos/index` | clone + chunk + embed + store a repo (idempotent) |
| GET | `/repos` | list indexed repos |
| POST | `/ask` | grounded Q&A with citations (cached for 1 hour) |
| POST | `/changes` | agent edits code, runs tests, optionally opens a PR |

## Cost notes

- Indexing a small repo (~300 chunks) costs a fraction of a cent with `text-embedding-3-small`.
- Each `/ask` is one `gpt-4o-mini` call — and repeat questions are free (cache).
- An agent run is a handful of `gpt-4o-mini` calls, bounded by `MAX_AGENT_STEPS`.

## Stretch ideas (great interview talking points)

- Per-answer **trust score** from retrieval distances
- **Structured pruning** of the index: skip generated/vendored files
- Swap Chroma for **Milvus**, SQLite for **PostgreSQL** — each is a one-module change
- Web UI on top of the same API
- Multi-repo chat by relaxing the `repo_id` filter
"# Gitpilot" 
