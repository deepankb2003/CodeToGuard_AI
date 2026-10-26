# CodeGuardian AI

A GitHub-webhook-driven PR reviewer. On every PR open/update it fetches the
diff, runs it through a LangGraph review graph (security, quality, test-gap,
and documentation agents in parallel), posts the aggregated findings as a PR
comment, and persists the result for later lookup.

## Architecture

```
GitHub webhook -> main.py -> review_graph (app/agents/graph.py)
                                 |
        +------------+----------+----------+-------------+
        |            |                     |             |
   security      quality (RAG)         test_gap     documentation
        |            |                     |             |
        +------------+----------+----------+-------------+
                                 |
                             aggregate -> PR comment + DB (app/db)
```

- **security** (`app/agents/security.py`) — runs Bandit + Semgrep against the
  PR's changed files, then has the LLM rewrite each raw finding in plain
  English.
- **quality** (`app/agents/quality.py`) — RAG-grounded: retrieves relevant
  excerpts from [`docs/coding_standards.md`](docs/coding_standards.md) (via
  Chroma, falling back to keyword overlap if Chroma's embedding model isn't
  available) and asks the LLM to flag only violations visible in the diff.
- **test_gap** (`app/agents/test_gap.py`) — heuristic: flags changed source
  files with no corresponding test file touched in the same PR.
- **documentation** (`app/agents/documentation.py`) — flags functions/classes
  added or modified in the diff that have no docstring.
- **aggregate** — merges all four findings lists, sorts by severity, and
  renders the PR comment body.

Results are persisted via `app/db` (SQLAlchemy) and exposed read-only through
`app/api/reviews.py` (`GET /reviews`, `GET /reviews/{id}`).

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirement.txt
cp .env.example .env     # fill in HUGGINGFACE_API_KEY, GITHUB_TOKEN, DATABASE_URL, etc.
```

`chromadb` needs a C/C++ toolchain to build its `chroma-hnswlib` dependency
(on Windows: the "Desktop development with C++" Visual Studio workload; on
Debian/Ubuntu: `build-essential`). If it's not available, the quality agent
still works — it falls back to a plain keyword-overlap retriever.

Run locally:

```bash
uvicorn main:app --reload
```

Run tests:

```bash
pytest
```

## Environment variables

See [`.env.example`](.env.example) for the full list — the important ones:

| Variable | Purpose |
|---|---|
| `HUGGINGFACE_API_KEY` | Powers security triage + RAG-grounded quality review (Hugging Face Inference API) |
| `GITHUB_TOKEN` | Fetch PR diffs / post PR comments |
| `GITHUB_WEBHOOK_SECRET` | Verifies `X-Hub-Signature-256`; blank skips verification (local dev only) |
| `DATABASE_URL` | Where reviews/findings are persisted |
| `CODING_STANDARDS_PATH` | Doc the quality agent's RAG index is built from |

## API

- `GET /` — the review-history dashboard (`app/static/`)
- `GET /health` — liveness check
- `POST /webhook/github` — GitHub PR webhook target
- `GET /reviews` — list past reviews (`?repo=owner/name` to filter)
- `GET /reviews/{id}` — a single review's report + findings

## Roadmap

1. **Project setup** — FastAPI app, config, GitHub client, DB/RAG dependencies.
2. **Graph scaffold** — LangGraph fan-out/aggregate wiring with stub agents.
3. **Security, test-gap, documentation agents** — real Bandit/Semgrep +
   LLM-triage, and diff-based heuristics.
4. **RAG-grounded quality agent** — retrieval over `docs/coding_standards.md`.
5. **Persistence** — SQLAlchemy models + review/finding storage.
6. **Review history API** — `GET /reviews`, `GET /reviews/{id}`.
7. **Tests, Docker, CI** — pytest suite, `Dockerfile`, GitHub Actions workflow.

All seven phases above are implemented in this repo.

## 🚀 Live Demo

Explore the deployed application here:

🔗 [**CodeToGuard AI — Live Application**](https://codetoguard-ai.onrender.com/)
