---
name: backend-development
description: Working on the RomM Python backend (backend/) — a FastAPI app with SQLAlchemy 2.0, Alembic, RQ/Redis, and Socket.IO. Use when adding or changing API endpoints, handlers, ORM models, response schemas, metadata-provider adapters, background tasks, database migrations, or backend tests. Covers the layered architecture, conventions, auth/scopes, the OpenAPI→frontend type pipeline, and the uv/pytest/alembic/trunk workflow. Trigger on any work under backend/.
---

# RomM Backend — FastAPI / SQLAlchemy

Python 3.13+, FastAPI, SQLAlchemy 2.0 (MariaDB default; MySQL/PostgreSQL supported), Alembic, Redis + RQ for jobs/cache/sessions, Socket.IO for real-time. Managed with **uv**.

Full reference: **`docs/BACKEND_ARCHITECTURE.md`** (directory map, ER diagram, every endpoint, auth flows). Read it before non-trivial changes.

---

## Layered architecture — where code goes

```txt
endpoints/        FastAPI routers: request validation, response schemas, @protected_route scopes
endpoints/responses/  Pydantic response schemas (these shape the OpenAPI → frontend types)
endpoints/sockets/    Socket.IO event handlers
handler/          Business logic, decoupled from HTTP
  ├ auth/         HybridAuthBackend (session/basic/bearer/OIDC/client-token), scopes, CSRF/session middleware
  ├ database/     Per-entity CRUD handlers (db_rom_handler, db_user_handler, …), engine/session factory
  ├ metadata/     One handler per provider; normalizes + ranks by priority
  └ filesystem/   ROM/asset/firmware file I/O, hashing, archive extraction
adapters/services/  Typed external API clients (igdb.py + igdb_types.py, screenscraper.py, …)
models/           SQLAlchemy ORM models (BaseModel adds created_at/updated_at)
tasks/            RQ jobs — scheduled/ (cron) and manual/ (on-demand); base classes in tasks.py
config/           Env-var loading (__init__.py) + YAML config manager (singleton)
decorators/       @begin_session (DB session), @protected_route (auth + scopes)
exceptions/       Custom exception hierarchy
utils/ logger/    Shared helpers, structured logging
alembic/          Migrations (env.py + versions/)
```

**Endpoint → handler → (database | metadata | filesystem) → models/adapters.** Endpoints stay thin: validate, enforce scopes, call handlers, serialize via a response schema. Don't put business logic or raw queries in endpoints.

## Conventions

- **Naming:** Classes `PascalCase`; functions/vars `snake_case`; constants `UPPER_SNAKE_CASE`; private `_prefixed`.
- **DB sessions:** decorate handler methods with `@begin_session`; it injects and manages the SQLAlchemy session/transaction. Don't open sessions ad hoc.
- **Async:** I/O-bound endpoints and tasks use `async/await`. Per-request `httpx`/`aiohttp` clients come from context vars (`utils/context.py`), not new clients per call.
- **Imports:** stdlib → third-party → local; explicit (no wildcards); `TYPE_CHECKING` blocks to break circular imports.
- **Errors:** raise the custom exceptions in `exceptions/` (e.g. `RomNotFoundInDatabaseException`), not bare `HTTPException`, where a typed one exists.
- **Validation/SSRF:** sanitize filenames/paths before filesystem use (`utils/`); paths are rooted at `LIBRARY_BASE_PATH`/`RESOURCES_BASE_PATH`/`ASSETS_BASE_PATH` from config.

## Auth & scopes

- Roles: `VIEWER` (read), `EDITOR` (+write roms/platforms/assets), `ADMIN` (+users/tasks/logs). Defined on `models/user.py`; scope tiers in `handler/auth/constants.py`.
- Granular scopes: `me.read/write`, `roms.read/write`, `platforms.*`, `assets.*`, `devices.*`, `firmware.*`, `collections.*`, `users.*`, `tasks.run`, `logs.read`.
- Protect routes with `@protected_route(router.<method>, "<path>", [Scope.X])`. The frontend mirrors these scopes — keep them aligned.

## Adding things

- **Endpoint:** add the route in the right `endpoints/*` router, a response schema in `endpoints/responses/`, enforce scopes, delegate to a handler. If the response shape changes, the frontend must regenerate types (below).
- **Model / schema change:** edit `models/`, then create a migration (below). Update the matching response schema so OpenAPI stays accurate.
- **Metadata provider:** add a typed client in `adapters/services/<name>.py` (+ `<name>_types.py`) and a `handler/metadata/<name>_handler.py` that normalizes into the common shape and slots into the priority order.
- **Background job:** subclass `Task`/`PeriodicTask` in `tasks/scheduled/` or `tasks/manual/`; register scheduled jobs in `startup.py`.

## Database migrations (Alembic)

Migrations must work on **MariaDB, MySQL, and PostgreSQL** (CI runs `alembic upgrade head` on Postgres and MariaDB — `.github/workflows/migrations.yml`). Use batch mode / DB-specific SQL where needed; mirror existing migrations in `alembic/versions/`.

```bash
cd backend
uv run alembic revision --autogenerate -m "short description"   # generate, then HAND-REVIEW the file
uv run alembic upgrade head                                     # apply
uv run alembic downgrade -1                                     # verify the downgrade works
```

Always review autogenerated migrations — they miss server-default/enum/index nuances and cross-dialect differences. The `virtual_collections` DB view is excluded from migrations.

## OpenAPI → frontend types

FastAPI serves the schema at `GET /openapi.json`. The frontend regenerates its TypeScript types from it:

```bash
# backend running on :3000, then in frontend/
npm run generate     # writes src/__generated__/ via openapi-typescript-codegen
```

**Any change to a response schema or route signature should be followed by `npm run generate` + a frontend typecheck.**

## Run, test, lint

```bash
cd backend
uv run python3 main.py            # run (migrations auto-apply on startup)
uv run pytest [path/file]         # tests (subset by path); uv run pytest -vv for all
```

- Tests: pytest + pytest-asyncio, isolated per `pytest-xdist` worker (per-worker DBs); `fakeredis`; `pytest-recording` VCR cassettes mock external APIs; Hypothesis for property tests. Mirror the `backend/<area>/` layout under `backend/tests/`. First-time test DB setup: `docker exec -i romm-db-dev mariadb -uroot -p<pw> < backend/romm_test/setup.sql`.
- **Lint / format / type-check run through Trunk** (ruff, black, isort, mypy, bandit): `trunk fmt && trunk check`. CI enforces Trunk on every PR. Never bypass with `--no-verify`.
- New/changed logic needs a test; new endpoints need endpoint tests.
