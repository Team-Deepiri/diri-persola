# AGENTS.md

Persola = agentic personality framework. Backend is a Poetry-managed Python package at the repo root; the web UI is a separate React+TS+Vite app in `ui/` (the root `package-lock.json` is an empty leftover — ignore it).

## Commands

Backend (root, Poetry):
- `poetry install` — install deps. Server entrypoints: `persola` (CLI) and `persola-server` = `persola.api.main:main`.
- `uvicorn persola.api.main:app --port 8002` — run API directly.
- `pytest` — run all tests. `pytest tests/unit/` / `tests/integration/` / `tests/e2e/` for subsets. No external services needed for any suite (SQLite in-memory + mocked LLM).
- `alembic upgrade head` — apply migrations (`DATABASE_URL` env drives `alembic/alembic.ini`).

UI (`ui/`):
- `npm install`, then `npm run dev` (Vite on :3000, proxies `/api` → `localhost:8010`), `npm run build` (`tsc && vite build`), `npm run lint` (ESLint, `--max-warnings 0`).

Docker: `docker-compose up` maps API → `8010`, Postgres → `5433`, UI → `3000`. Backend serves the built UI at `/ui` and `/static` when `ui/dist` is copied in.

## Tests — critical env detail

`persola/db/database.py` reads `DATABASE_URL` at import time and raises `RuntimeError` if unset. `tests/conftest.py` sets `DATABASE_URL=sqlite+aiosqlite:///:memory:` **before** any `persola` import and registers a JSONB→JSON compiler so Postgres-specific columns work on SQLite. Follow that pattern if adding a new test entrypoint or standalone script.

- `pytest` runs with `asyncio_mode = "auto"` (`pyproject.toml`) — no `@pytest.mark.asyncio` needed; `anyio_backend` fixture forces asyncio.
- `http_client` fixture overrides the `get_db` dependency with a per-test session; ASGITransport never triggers app lifespan (`init_db`/`close_db`).
- Coverage gate: `fail_under = 80`.

## DB & migrations

- Schema lives in `persola/db/models.py`; migrations in `alembic/versions/` numbered `001`–`005`. Adding a table/column requires a new alembic revision; `init_db()` at app startup also runs `Base.metadata.create_all`, so mismatched schemas are easy to miss.
- Migrate-on-boot only runs in Docker when `PERSOLA_AUTO_MIGRATE=1` (`docker/entrypoint.sh`).
- For new city/orchestration features, follow the docs in `docs/` (Communal City design, schema map, DB implementation) before touching models.

## Config & auth

- LLM settings are file-backed: `.persola/settings.json` (gitignored) merged with env, env wins on empty fields (`persola/integrations/llm_settings.py`). `load_llm_settings()` caches — pass `force=True` after saving. Default provider is Ollama.
- Auth: `PERSOLA_API_KEYS` = comma-separated keys; when unset auth is disabled. Exempt paths: `/health`, `/`, `/ui`, `/static`, `/metrics`, `/api/v1/city/health`.
- Rate limits: `/agents/{id}/invoke` = 30/min (slowapi + in-memory token bucket), `/analysis/extract` = 10/min.

## Git conventions

- `.git-hooks/` is the hooks dir (`core.hooksPath` auto-set on checkout). `pre-push` **blocks pushes to `main`/`master`** (exact match). Work on a feature branch and merge via PR (see `.github/workflows/codeql.yml` — the only CI, and it's effectively skipped).
- Recent history shows branch naming like `name/feature/<slug>` and `name-dev`.

## Style

- Formatters: black + ruff, line length 100 (`pyproject.toml`).
- Indentation is mixed: tabs in the city/orchestration, `db/`, and `integrations/` files; 4 spaces in `api/main.py`, `analysis/`, `cli/`, and tests. Match the file you're editing.
