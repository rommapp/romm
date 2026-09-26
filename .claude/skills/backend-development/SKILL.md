---
name: backend-development
description: Working on the RomM Python backend (backend/) — a FastAPI app with SQLAlchemy 2.0, Alembic, RQ/Redis, and Socket.IO. Use when adding or changing API endpoints, handlers, ORM models, response schemas, metadata-provider adapters, background tasks, database migrations, or backend tests. Covers the layered architecture, conventions, auth/scopes, the OpenAPI→frontend type pipeline, and the uv/pytest/alembic/trunk workflow. Trigger on any work under backend/.
---

# RomM Backend — FastAPI / SQLAlchemy

Python 3.14+, FastAPI, SQLAlchemy 2.0 (MariaDB default; MySQL/PostgreSQL supported), Alembic, Redis + RQ for jobs/cache/sessions, Socket.IO for real-time. Managed with **uv**.

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
- **Engine-specific query SQL:** reach for a portable SQLAlchemy expression first. If the engines need different SQL, build both with `DialectCase(postgresql=..., mysql=...)` from `utils/sql_dialect.py` (or add a helper or `@compiles` construct there) rather than branching on `ROMM_DB_DRIVER` in a handler. `@compiles(..., "mysql")` alone misses MariaDB; use `_compiles_on_mysql_family`. Pin each spelling in tests by compiling for `MARIADB_DIALECT`/`POSTGRESQL_DIALECT` from `tests/handler/database/conftest.py`.

## Auth & scopes

- Roles: `VIEWER` (read), `EDITOR` (+write roms/platforms/assets), `ADMIN` (+users/tasks/logs). Defined on `models/user.py`; scope tiers in `handler/auth/constants.py`.
- Granular scopes: `me.read/write`, `roms.read/write`, `platforms.*`, `assets.*`, `devices.*`, `firmware.*`, `collections.*`, `users.*`, `tasks.run`, `logs.read`.
- Protect routes with `@protected_route(router.<method>, "<path>", [Scope.X])`. The frontend mirrors these scopes — keep them aligned.

## Adding things

- **Endpoint:** add the route in the right `endpoints/*` router, a response schema in `endpoints/responses/`, enforce scopes, delegate to a handler. If the response shape changes, the frontend must regenerate types (below).
- **Model / schema change:** edit `models/`, then create a migration (below). Update the matching response schema so OpenAPI stays accurate.
- **Metadata provider:** add a typed client in `adapters/services/<name>.py` (+ `<name>_types.py`) and a `handler/metadata/<name>_handler.py` that normalizes into the common shape and slots into the priority order.
- **Background job:** subclass `Task`/`PeriodicTask` in `tasks/scheduled/` or `tasks/manual/`; register scheduled jobs in `startup.py`.
- **Telling a user something happened:** `notify()` / `notify_admins()` in `handler/notification_handler.py`, from a request or a worker. A `NotificationKind` is translated client-side from `data` (add its describer and locale keys); for anything else pass a free-form kind with `title`/`body`/`link`.

## Database migrations (Alembic)

Migrations must work on **MariaDB, MySQL, and PostgreSQL** (CI runs `alembic upgrade head` on Postgres and MariaDB — `.github/workflows/migrations.yml`). Use batch mode / DB-specific SQL where needed; mirror existing migrations in `alembic/versions/`.

```bash
cd backend
uv run alembic revision --autogenerate -m "short description"   # generate, then HAND-REVIEW the file
uv run alembic upgrade head                                     # apply
uv run alembic downgrade -1                                     # verify the downgrade works
```

Always review autogenerated migrations — they miss server-default/enum/index nuances and cross-dialect differences. The `virtual_collections` DB view is excluded from migrations.

### Migration hygiene (recurring review fixes)

- **Numbering collides on rebase.** Two open branches both pick the next number. When you rebase onto `master` and find your `0102_*` already taken, rename the file, update `revision`, and re-chain `down_revision` onto the migration that actually precedes it now. Then run `alembic upgrade head` on a fresh DB to confirm the chain is linear.
- **Use the builtin idempotency flags, not manual introspection.** `op.create_table(..., if_not_exists=True)` and `create_index(..., if_not_exists=True)` over `inspect(conn).get_table_names()` guards wrapping the whole block. Reserve `inspect()` for what the flags can't express.
- **A released revision must survive a partial run.** MySQL/MariaDB auto-commit each DDL statement while alembic only stamps on success, so a revision that dies partway leaves its earlier statements behind and the next start replays it from the top. Guard every step, and filter raw `op.execute("ALTER TABLE ...")` strings against `utils.database.column_names` where the flags cannot reach. `tests/test_migrations.py` pins the replays.
- **Edit an unreleased migration in place.** If the migration hasn't shipped in a tag yet, change it rather than stacking a fixup migration on top. Only released migrations are immutable.
- **Don't ship a data backfill you can avoid.** A rewrite-every-row migration to normalize values the parser now handles is a maintenance liability. Prefer fixing the parser and letting the next scan converge, unless stale rows are actually user-visible and unrecoverable.
- **A new `roms` column goes through `utils/roms_columns.py`.** Declare it in the catalog there and have the revision call `ensure_roms_columns()`; the first revision that runs on a database adds every catalog column the table lacks in one `ALTER TABLE`. `roms` carries a FULLTEXT index and JSON blobs per provider, so each separate `ALTER TABLE roms` copies the whole table, minutes per copy on a scraped library. The revision's downgrade drops its own column with `if_exists=True`; `0108`'s downgrade calls `drop_roms_columns()` and removes whatever of the catalog a chain that stopped short still carries.
- **Prefer a generated column plus an index over a join** when a field exists only to sort or filter (see `generated_first_release_date`), and say so in the model's `__table_args__` rather than in prose.
- **Pass `nullable=` on every database-filled column.** A `mapped_column(server_default=FetchedValue())` left to infer it from `Mapped[...]` is one autogenerate never compares, so declare it to match the DDL (MariaDB forces generated columns nullable). `tests/test_migrations.py` enforces it.

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
uv run pytest <path/file>         # tests - affected files only, NEVER the whole suite
```

- Tests: pytest + pytest-asyncio, isolated per `pytest-xdist` worker (per-worker DBs); `fakeredis`; `pytest-recording` VCR cassettes mock external APIs; Hypothesis for property tests. Mirror the `backend/<area>/` layout under `backend/tests/`. First-time test DB setup: `docker exec -i romm-db-dev mariadb -uroot -p<pw> < backend/romm_test/setup.sql`.
- **Lint / format run through Trunk** (ruff, black, isort, bandit): `trunk fmt && trunk check`. CI enforces Trunk on every PR. Never bypass with `--no-verify`.
- **Type-check with mypy**, outside Trunk so it sees the project's packages: `uv run mypy --config-file ../.trunk/configs/mypy.ini .` from `backend/`. CI's `mypy.yml` requires zero errors.
- New/changed logic needs a test; new endpoints need endpoint tests.
