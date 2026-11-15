# RomM Backend Architecture

How the RomM backend fits together: its layers, request flow, auth model, scanning, real-time channels and background work.

This document describes design and rules that change slowly. Facts that change with most pull requests live in the code, which is their only source:

| For                          | Read                                                                |
| ---------------------------- | ------------------------------------------------------------------- |
| Every route, scope and shape | Swagger UI at `/api/docs`, ReDoc at `/api/redoc`, or `endpoints/`   |
| Tables and columns           | `models/`, and `alembic/versions/` for how they got there           |
| Scopes                       | `Scope` in `handler/auth/constants.py`                              |
| Environment variables        | `env.template` at the repository root, read in `config/__init__.py` |
| `config.yml` keys            | `examples/config.example.yml`, read by `config/config_manager.py`   |
| Scheduled and manual tasks   | `tasks/registry.py`                                                 |
| Exceptions                   | `exceptions/`                                                       |
| Dependency versions          | `pyproject.toml` and `uv.lock`                                      |

---

## Table of Contents

1. [Overview](#1-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Application Lifecycle](#3-application-lifecycle)
4. [Database Layer](#4-database-layer)
5. [API Conventions](#5-api-conventions)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [Business Logic (Handlers)](#7-business-logic-handlers)
8. [External Integrations (Adapters)](#8-external-integrations-adapters)
9. [Real-Time Communication (WebSockets)](#9-real-time-communication-websockets)
10. [Background Tasks & Scheduling](#10-background-tasks--scheduling)
11. [File System Management](#11-file-system-management)
12. [Caching (Redis)](#12-caching-redis)
13. [Configuration, Errors & Logging](#13-configuration-errors--logging)
14. [Testing](#14-testing)

---

## 1. Overview

| Property        | Value                                              |
| --------------- | -------------------------------------------------- |
| **Framework**   | FastAPI                                            |
| **ORM**         | SQLAlchemy 2.1, migrations with Alembic            |
| **Databases**   | MariaDB, MySQL, PostgreSQL                         |
| **Cache/Queue** | Redis or Valkey, jobs on RQ                        |
| **Real-time**   | Socket.IO (python-socketio)                        |
| **Auth**        | Session, Basic, OAuth2 bearer, OIDC, client tokens |
| **ASGI Server** | Uvicorn / Gunicorn                                 |

RomM's backend is responsible for:

- **Library scanning**: detecting platforms and ROMs from the filesystem
- **Metadata enrichment**: pulling game info from 10+ external providers
- **User management**: permission groups, authentication, per-user game tracking
- **Asset management**: saves, save states, screenshots, firmware/BIOS
- **Device sync**: cross-device save synchronization
- **Netplay**: real-time multiplayer room coordination
- **Feed generation**: Tinfoil, WebRcade, PKGi, and other custom formats

---

## 2. High-Level Architecture

```text
                                 +---------------------+
                                 |     Nginx / CDN     |
                                 |  (reverse proxy,    |
                                 |   X-Accel-Redirect) |
                                 +----------+----------+
                                            |
                                            v
                              +-------------+--------------+
                              |     FastAPI Application     |
                              |        (main.py)            |
                              +-------------+--------------+
                                            |
              +-----------------------------+------------------------------+
              |                             |                              |
     +--------v--------+         +---------v----------+         +---------v--------+
     |   Middleware     |         |   API Routers      |         |   WebSockets     |
     |  Stack           |         |                    |         |  /ws  /netplay   |
     +---------+--------+         +---------+----------+         +---------+--------+
               |                            |                              |
               v                            v                              v
     +-------------------+      +-----------+-----------+       +----------+---------+
     | Context Vars      |      |    Endpoint Layer     |       |  Socket.IO Server  |
     | Session (Redis)   |      | (request validation,  |       |  (scan progress,   |
     | Authentication    |      |  response schemas)    |       |   netplay rooms)   |
     | CSRF              |      +-----------+-----------+       +----------+---------+
     | Upload size, CORS |                  |                              |
     +-------------------+                  v                              |
                              +-------------+--------------+               |
                              |     Handler Layer          |               |
                              | (business logic, CRUD,     |<--------------+
                              |  metadata, filesystem)     |
                              +------+-------+------+------+
                                     |       |      |
                  +------------------+       |      +------------------+
                  |                          |                         |
         +--------v--------+     +----------v----------+    +---------v---------+
         |   Database       |     |   External APIs     |    |   File System     |
         |  (SQLAlchemy)    |     |  (metadata          |    |  (ROM library,    |
         |                  |     |   providers)        |    |   assets, BIOS)   |
         | MariaDB/MySQL/PG |     +---------------------+    +-------------------+
         +---------+--------+
                   |
                   v
         +-------------------+
         |     Redis          |
         | (sessions, cache,  |
         |  job queues, rooms)|
         +-------------------+
```

### Layered Architecture

```text
+-----------------------------------------------------------------------+
|                         PRESENTATION LAYER                             |
|  endpoints/          API route handlers, request/response schemas      |
|  endpoints/sockets/  WebSocket event handlers                          |
+-----------------------------------------------------------------------+
|                         BUSINESS LOGIC LAYER                           |
|  handler/auth/       Authentication & authorization                    |
|  handler/database/   CRUD operations per entity                        |
|  handler/metadata/   Metadata fetching & normalization                 |
|  handler/filesystem/ File system operations                            |
|  handler/            Scan orchestration, netplay, sockets, sync        |
+-----------------------------------------------------------------------+
|                         DATA ACCESS LAYER                              |
|  models/             SQLAlchemy ORM model definitions                  |
|  adapters/services/  External API client wrappers                      |
|  handler/redis_handler.py  Cache & queue operations                    |
+-----------------------------------------------------------------------+
|                         INFRASTRUCTURE LAYER                           |
|  config/             Environment variables & YAML config               |
|  decorators/         Auth & DB session decorators                      |
|  exceptions/         Custom exception hierarchy                        |
|  logger/             Structured logging                                |
|  utils/              Shared helpers (hashing, context, validation)     |
|  tasks/              Background job definitions & scheduling           |
+-----------------------------------------------------------------------+
```

Endpoints call handlers; handlers own every query, file write and provider call. `tools/` holds dev and test scripts outside the app runtime.

---

## 3. Application Lifecycle

### Startup Sequence

```text
1. alembic upgrade head          # Run database migrations
2. startup.main()                # Async startup tasks
   ├── Clear stale delayed scans and legacy scheduler keys
   └── Load fixture caches into Redis (MAME, ScummVM, console serials, known BIOS)
3. uvicorn.run("main:app")       # Start ASGI server
   └── FastAPI lifespan
       ├── Create aiohttp.ClientSession
       ├── Create httpx2.AsyncClient
       └── Store in app.state + context vars
```

### Middleware Stack

Registered in `main.py`. Starlette runs the last-registered middleware outermost, so a request passes through them in this order:

```text
Request → Context Vars → Session (Redis) → Authentication → CSRF → Upload size limits → CORS → Endpoint
```

| Middleware                  | Purpose                                                     |
| --------------------------- | ----------------------------------------------------------- |
| `set_context_middleware`    | Inject the aiohttp/httpx2 clients into context vars         |
| `RedisSessionMiddleware`    | Cookie-based sessions stored in Redis                       |
| `AuthenticationMiddleware`  | `HybridAuthBackend`: session, Basic, Bearer, OIDC, kiosk    |
| `CSRFMiddleware`            | Token-based CSRF protection; off in tests and when disabled |
| `UploadSizeLimitMiddleware` | Cap request bodies on upload routes                         |
| `CORSMiddleware`            | Cross-origin requests                                       |

### Request Flow

```text
HTTP Request
    │
    ├─ Middleware processes request (session, auth, CSRF)
    │
    ├─ FastAPI routes to endpoint handler
    │   └─ @protected_route checks scopes
    │
    ├─ Endpoint checks permissions and visibility, then calls the handler layer
    │   ├─ handler/database/*   → SQLAlchemy queries
    │   ├─ handler/metadata/*   → External API calls
    │   ├─ handler/filesystem/* → File I/O
    │   └─ handler/auth/*       → Token operations
    │
    ├─ Response schema (Pydantic) serializes output
    │
    └─ HTTP Response
```

---

## 4. Database Layer

### Supported Databases

| Database       | Driver                     | Status    |
| -------------- | -------------------------- | --------- |
| MariaDB 10.11+ | `mariadb+mariadbconnector` | Default   |
| MySQL 8.0.17+  | `mysql+mysqlconnector`     | Supported |
| PostgreSQL     | `postgresql+psycopg`       | Supported |

MariaDB 10.5 and 10.6 reached upstream end of life in June 2025 and July 2026, so
10.11 is the oldest LTS still receiving fixes.

CI runs the test suite against MariaDB and PostgreSQL, and the migration suite
additionally against MariaDB 10.11, which predates the 11.6 `uca1400` collation
default. MySQL has no CI coverage.

Query SQL that differs between engines lives in `utils/sql_dialect.py`
(`DialectCase` and the helpers built on it), which picks each engine's spelling
when the statement compiles. Handlers don't branch on `ROMM_DB_DRIVER`.

`utils/fulltext.py` reads InnoDB's full-text token sizes and stopwords from the
server and splits search words the way its parser does, so a search can require
the words a FULLTEXT index holds and check the rest with `LIKE`.

### Engine & Session Setup

The engine and `sync_session` live in `handler/database/base_handler.py`, with
`pool_pre_ping` on and `expire_on_commit` off. Handler methods get their session
from the `@begin_session` decorator, which wraps each call in a transaction.
Every model inherits `BaseModel` (`models/base.py`), which adds `created_at` and
`updated_at` as timezone-aware UTC timestamps.

### Models

`models/` holds one module per entity family. The core relationships:

- A **platform** owns its **roms** and its **firmware**.
- A **rom** owns its files, aggregated metadata and notes, and relates to sibling roms.
- A **user** owns saves, states and screenshots (each tied to a rom), per-rom user data, collections, devices, client tokens and play sessions.
- A **channel** is one playthrough of one ROM file, keyed by its SHA-1 (or name and size when unhashed). It points at its current **snapshot**, a fixed save plus a bank of states (`snapshot_states`); earlier snapshots form its history and stale pushes become branches. Devices record the snapshot they hold per channel (`device_channel_sync`), and pins keep a snapshot from pruning.
- **Collections** come in three kinds: hand-picked (`collections_roms`), smart (saved filters) and virtual (a view over metadata).
- **Permission groups** hold entity and action grants, hidden entities and age settings. A user adds their own grant overrides and hidden entities, and their age settings replace the group's when set.

Every schema change ships as an Alembic migration in `alembic/versions/`.

---

## 5. API Conventions

- **Base URL** `/api`. The OpenAPI schema is the contract: the frontend generates its types from it (`npm run generate`).
- **Registration.** Every authenticated route is registered through `@protected_route(router.<method>, path, [scopes])` in `decorators/auth.py`, which adds the bearer and Basic security dependencies and checks the scopes. A route that answers callers with no credential (login, token, password reset, invite, pairing, heartbeat, public config, the RetroArch WebDAV router) is registered with the bare router and checks its caller itself.
- **Trailing slashes.** `utils/router.APIRouter` registers each path with and without a trailing slash instead of redirecting.
- **Pagination.** `PageParams` (`limit`, `offset`) through the `PAGE_QUERY` dependency, returning a `LimitOffsetPage` (`items`, `total`, `limit`, `offset`); both live in `endpoints/responses/base.py`. Routes with a smaller page cap subclass `PageParams` (`MusicPageParams`, `AuditPageParams`).
- **Hidden reads as missing.** A rom, platform or firmware hidden from the caller answers exactly as a missing id would (see [Visibility](#visibility-is-access-control)).
- **Chunked uploads.** Large ROM uploads go through `/api/roms/upload/start`, chunk `PUT`s, then `complete` or `cancel` (`endpoints/roms/upload.py`).
- **Audit trail.** Events are written by `handler/audit_handler.record()` after an action succeeds, and a failure to write never fails the action. A ROM content fetch is a `rom.download`, or a `rom.player_load` when the in-browser player marks it `purpose=play`; a fetch whose Range starts past byte 0, or that the same caller made in the last 10 minutes, isn't recorded. A failed login keeps the attempted name only when an account has it. The client address comes from `X-Forwarded-For` only when the connection is from a proxy in `FORWARDED_ALLOW_IPS`.

### Download conversion

With rom-converto enabled (`ROM_CONVERTO_ENABLED`, `converto.download_conversion_enabled`), `?format=zso,iso` lists the formats a client can read. A single-file download whose stored format is listed is served as-is. Otherwise the first listed format with a copy cached under `/tmp/romm/cache/converts` (`$ROMM_TMP_PATH/cache/converts` when set) is served, then the first one rom-converto can produce: answered by the same request if it converts within a few seconds, else `202` with `Retry-After` while it finishes. `406` means no listed format can be served, and `HEAD` reports the same without starting a conversion. Only signed-in, non-kiosk users start conversions. A rom's detail response lists the formats its single file can be converted to in `download_formats`, empty when the caller can't start a conversion.

### Queueing a scan over HTTP

`POST /api/tasks/scan` takes the options of the `scan` socket event and answers 202 with the queued job; `GET /api/tasks/{id}` follows it, with the counts so far in `meta.scan_stats`. A missing body means a quick scan of the whole library, a missing `apis` every enabled metadata source, and an unknown key answers 422. A scan of named `roms_ids` goes ahead of a queued library scan; any other scan answers 409 while a library scan is queued or running. It answers 503 when no worker listens on the scan queue.

---

## 6. Authentication & Authorization

### Authentication Methods

```text
┌──────────────────────────────────────────────────────────────┐
│                    HybridAuthBackend                          │
│                                                              │
│  1. Check session cookie (romm_session)                      │
│     └─ Redis lookup → user from session["sub"]               │
│                                                              │
│  2. Check Authorization header                               │
│     ├─ "Basic ..." → password verify                         │
│     ├─ "Bearer ..." → JWT validation (HS256)                 │
│     └─ "Bearer rmm_..." → Client API token (SHA-256 lookup)  │
│                                                              │
│  3. OIDC (if enabled)                                        │
│     └─ Token from OIDC provider → email match → user         │
│                                                              │
│  4. Kiosk mode (if enabled)                                  │
│     └─ Anonymous access with read-only scopes                │
│                                                              │
│  Falls through all methods → unauthenticated                 │
└──────────────────────────────────────────────────────────────┘
```

### Token Types

Lifetimes are the defaults; each is configurable (see `env.template`).

| Token            | Format                | Default lifetime | Storage                 |
| ---------------- | --------------------- | ---------------- | ----------------------- |
| Access Token     | JWT (HS256)           | 30 min           | Client-side             |
| Refresh Token    | JWT with JTI          | 7 days           | JTI in Redis            |
| Session          | Cookie `romm_session` | 14 days          | Redis                   |
| Client API Token | `rmm_` + 64 hex chars | Set per token    | SHA-256 hash in DB      |
| CSRF Token       | Signed cookie         | Session lifetime | Cookie + header         |
| Password Reset   | JWT with JTI          | 10 minutes       | JTI in Redis (one-time) |
| Invite Link      | JWT with JTI          | 10 minutes       | JTI in Redis (one-time) |

A reset link is emailed when SMTP is set up, the user has an address and `ROMM_BASE_URL` is shareable, at most once a minute per user; otherwise it goes to the log for an admin to pass on. It is built from `ROMM_BASE_URL`, never the request's `Host`.

### Roles, Scopes and Permission Groups

There are two roles (`models/user.py`): `admin` bypasses every permission check, and `user` gets its access entirely from a **permission group** plus per-user overrides (`handler/auth/permissions.py`). The old viewer and editor roles are now system permission groups.

Two layers apply to every request:

1. **Scopes** (`Scope` in `handler/auth/constants.py`) on the credential, checked by `@protected_route`. A user's scopes are projected from their group and overrides (`User.oauth_scopes`), so they shrink when the group does.
2. **Grants** in the caller's permission group: entity and action grants, optionally "own items only", checked in the endpoint (`handler/auth/dependencies.py`).

Most entities line up with a scope; `streaming` and `emulation` have none. A `read` grant shows streaming and lets the user join someone else's session, while an "own items only" `read` shows it without the join. Starting a session takes `read` and `write`. A user who loses the grant keeps control of a session they already hold.

`emulation` covers the in-browser players (EmulatorJS, Ruffle, js-dos, PICO-8, EasyRPG). A `read` grant lets the user play in the browser and join someone else's netplay room, and an "own items only" `read` plays without the join. Hosting a room takes `read` and `write`. A password room admits anyone with the password, so the invite stands in for the grant. ROM files are also served for downloads, so the grant hides the players in the UI and is enforced on the netplay sockets, the room list and the EasyRPG file route.

### Visibility is access control

A rom or platform hidden from a user, directly or by age limit, must be unreachable for them, not only absent from lists. Firmware follows its platform.

- A single fetch calls `assert_rom_visible`, `assert_platform_visible` or `assert_firmware_visible`. Each raises a 404, never a 403, so a hidden entity reads as a missing one.
- A list query filters by the caller's `RomVisibilityFilter` in SQL, before any limit. Handler queries take the filter as a required argument, and a system caller passes `UNRESTRICTED` explicitly.
- A save, state or screenshot reached only by its owner goes through `owned_rom_asset_or_404`. A download that also serves public assets checks owner-or-public itself, then calls `assert_rom_visible`, so sharing never overrides rom visibility.
- A socket broadcast goes to the rom's audience only.

Files under `/assets/romm/resources/` are served by nginx without auth and are out of scope.

### CSRF Protection

- Cookie `romm_csrftoken` (signed with `itsdangerous`) and header `x-csrftoken` must match and carry the authenticated user's ID.
- Skipped for requests with an `Authorization: Bearer` or `Basic` header, and for the token exchange, pairing status and socket paths (see `CSRFMiddleware` for the exempt list).

### Session Management

- Redis keys: `session:{session_id}`, `user_sessions:{username}`, `session_sockets:{channel}:{session_id}`
- Cookie: `romm_session` (httponly, samesite lax with OIDC, strict otherwise)
- `clear_user_sessions(user_id)` on password change clears all sessions
- Removing a session (logout, revoke) disconnects the sockets it opened on both `/ws` and `/netplay`, which would otherwise keep their `user:{id}` and `admin` rooms or their netplay access

---

## 7. Business Logic (Handlers)

### 7.1 Scanning (`handler/scan_handler.py`, `handler/scan/`)

The core of RomM. Orchestrates library scanning and metadata enrichment. The scan types, metadata sources and rescan rules live in `handler/scan/sources.py`, the per-source lookups in `handler/scan/lookups.py`, and the merge of their answers into a rom's columns in `handler/scan/merge.py`.

| Type            | Behavior                                                                                  |
| --------------- | ----------------------------------------------------------------------------------------- |
| `NEW_PLATFORMS` | Detect new platform folders only                                                          |
| `QUICK`         | Scan new ROMs and reconcile the files of existing ones, hashing only new or changed files |
| `UPDATE`        | Rescan already-identified ROMs                                                            |
| `UNMATCHED`     | Rescan ROMs without metadata                                                              |
| `COMPLETE`      | Full rescan of everything                                                                 |
| `HASHES`        | Recalculate all file hashes                                                               |

```text
1. Detect platform folders in the library
2. For each platform:
   ├── Map filesystem slug to canonical platform (via config bindings)
   ├── Query metadata providers for platform info
   └── Create/update platform in DB
3. For each ROM in the platform:
   ├── Parse filename (extract name, tags, region, version)
   ├── Calculate file hashes
   ├── Search the enabled metadata providers in priority order
   ├── Download cover art and screenshots
   ├── Build aggregated metadata (RomMetadata)
   └── Create/update ROM in DB
4. Emit real-time progress via Socket.IO
5. Mark missing ROMs (files no longer on filesystem)
```

Search terms drop articles and punctuation and are NFKD-normalized; fuzzy results are ranked by Jaro-Winkler similarity.

### 7.2 Database Handlers (`handler/database/`)

One `db_*_handler` per entity family owns its queries and writes: filtering and pagination for roms, slug mapping for platforms, slot grouping for saves, fingerprint deduplication for devices, and so on. Endpoints and tasks never build queries themselves.

### 7.3 Metadata Handlers (`handler/metadata/`)

One handler per provider normalizes its answers into RomM's fields. Sources are queried in the priority order set in `config.yml` (`scan.priority`); the first match wins for each field, and manual overrides take precedence over all of them.

### 7.4 Filesystem Handlers (`handler/filesystem/`)

Handlers for roms, assets, firmware, platforms and resources share `FSHandler` (`base_handler.py`). Every path built from caller input goes through `validate_path`, which refuses parent references and absolute paths and keeps the result inside the handler's base folder; a symlink an admin placed inside the base is followed on purpose.

Hashing notes:

- CHD v5: SHA1 read from the header
- PICO-8 cartridges (`.p8.png`): special handling
- RetroAchievements hash (`ra_hash`): platform-specific algorithm via `rahasher.py`
- Non-hashable platforms (Switch, PS3/4/5): hashing skipped

### 7.5 Play Sessions

Tracks per-user playtime events ingested from clients (web player, console mode, external launchers) via `POST /api/play-sessions`. Persisted in `play_sessions`; aggregated into user profile stats and recent-activity feeds.

### 7.6 Device Sync

Coordinates save/state synchronization between devices using three sync modes (`API`, `FILE_TRANSFER`, `PUSH_PULL`). `SyncSession` tracks the lifecycle of a push/pull operation, including optional SSH-based file transfer (`SYNC_SSH_*`). Endpoints live in `endpoints/sync/__init__.py`.

### 7.6a Save Channels and Snapshots (`handler/snapshots/`)

Clients opt into snapshots by pushing to `/api/snapshots`; a slotted upload through `/saves` files the save under the slot's channel with no snapshot. Saves and states a snapshot holds are immutable: writes to them through the legacy routes answer 409 (423 over WebDAV).

- **Writes:** every snapshot goes through `write.write_snapshot`, which locks the channel row and checks the expected current. A stale push is kept as a branch and answered 409 (`moved`, or `moved_from_older` when its parent is older than the current). A push without an explicit expected current infers it from its parent, the device's held snapshot, or the current the device last learned. A push that adds no progress answers unchanged. Hardcore channels refuse a softcore current.
- **Legacy bridge:** once a channel has a current, legacy clients join it (`bridge.py`). Negotiate decides a slot from the channel's history and the snapshot the device holds: a save matching an earlier current is behind, one matching a branch conflicts, and an unknown one uploads from a device on the current and conflicts from one on an older snapshot. A slotted upload becomes the next current and carries the parent's states. Hardcore channels and neutral current saves stay out.
- **Sharing:** a public channel is readable and writable by every user. The snapshot belongs to the channel owner and records the pusher as author; content reuse by hash only looks inside the channel, so a pusher can't pull in the owner's other saves.
- **Shared cards and uploads:** a PS1, PS2 or GameCube memory card holding other games' saves is cut to the game's neutral unit before the write (`shared_card.py`), and identity hashes, the digest and reuse all use that unit. Every uploaded zip passes `check_zip`, and a neutral unit also passes `check_neutral_unit`.
- **Retention:** each push keeps the channel's newest `SNAPSHOT_RETENTION`, and the `prune_snapshots` task drops old branches. Pruning deletes the content rows only pruned snapshots held. Deleting a channel keeps its current and owner-pinned snapshots as archival; an archival snapshot whose ROM was removed returns when a scan finds a file with its `rom_sha1`.

### 7.7 RetroArch Cloud Sync (`/api/sync/retroarch`)

A minimal WebDAV surface for RetroArch's Cloud Sync driver, which diffs a JSON
manifest of `{path, hash}` entries instead of listing collections. Point
RetroArch's WebDAV URL at `https://<host>/api/sync/retroarch/` (trailing slash
required) and authenticate with a RomM username and password over HTTP Basic.
Saves and states live under `saves/` and `states/`; `config/`, `thumbnails/` and
`system/` are opaque blobs.

- **Matching:** a file matches a ROM by file name alone (`Super Mario World.srm`
  matches `fs_name_no_ext` `Super Mario World`), so a name shared across
  platforms resolves to the lowest visible ROM id.
- **Cores:** the `core` segment is RetroArch's directory name (e.g. `Snes9x`),
  mapped to and from the asset's `emulator` through
  `sync.retroarch.emulator_names`, so web player saves stay visible. Unknown
  cores round-trip unchanged. Every `emulator` that maps to one folder (e.g.
  `mednafen_psx_hw`, `beetle_psx_hw` and `Beetle PSX HW`) is an alias: the
  manifest lists the newest asset across them, and GET, PUT and DELETE resolve
  a path across them. A PUT stores new assets under the folder's canonical id
  and rewrites an existing one under its own.
- **Save slots:** a `.srm` path maps to the `autosave` versions of its ROM and
  core, listed under the client's spelling of the game (or the ROM's name).
  Once a version exists, the path serves the `default` channel's current save
  when it is native and `may_load` for that core, else the newest version. An
  unslotted save at that path serves only until a version exists. A PUT whose
  bytes differ from the save the path serves adds a version, which files under the
  `default` channel and becomes its next snapshot through `hold_legacy_upload`,
  then prunes that lineage (emulator and extension) to `MAX_SAVES_PER_SLOT`.
  A DELETE removes every
  `autosave` version of it plus the unslotted save. Named slots are never
  touched. Other files (`.rtc`, core-specific saves) and PSP bundles stay single
  unslotted saves, overwritten in place.
- **Held rows:** a save or state a channel snapshot holds is never rewritten or
  deleted. A PUT over a held unslotted save returns 423, a state or PSP bundle
  upload writes a new copy beside it, and a DELETE skips it, answering 423 when
  only held rows are at the path.
- **Version names:** `reserve_version_name` moves a taken tag on a second and
  claims it in Redis, so concurrent or same-second uploads from any endpoint
  never share a file. Every slot prune is scoped to the uploaded save's lineage.
- **Manifest:** assets whose file is gone are flagged `missing_from_fs`. Hashes
  are MD5s of the bytes on disk, Redis-cached by path, size and mtime. A state
  slot lists and serves its newest state on disk, and a PUT revives a newer
  missing one in place. A manifest or GET that finds a file gone flags it and
  resolves again, so an older asset at that path takes its place.
- **PSP:** PPSSPP's `PSP/SAVEDATA/<folder>/` files are stored as one zipped
  `Save` per folder. A folder whose title matches no ROM is buffered in the
  user's `retroarch/psp_pending/` folder until it resolves, or mapped through
  `SYNC_RETROARCH_PSP_SERIAL_MAP`. Clients can't reach `psp_pending/`.
- **Blobs:** `config/`, `thumbnails/` and `system/` belong to no ROM, so they
  are stored per user under `assets/users/<user>/retroarch/` (`FSRetroArchSyncHandler`).
- **Auth:** the router gates itself through `_authorize` so it can answer a 401
  Basic challenge, and sends body-less errors, which RetroArch's client needs.
  The kiosk guest may browse `roms/` but is challenged everywhere else. Uploads
  are capped at `MAX_ASSET_UPLOAD_SIZE_BYTES`.
- **Device:** each manifest fetch registers or touches one RetroArch `Device`
  per user (`client="retroarch"`, `SyncMode.API`), since RetroArch sends no
  install identity.

### 7.8 Socket Handler (`handler/socket_handler.py`)

Two Socket.IO servers, both backed by Redis for horizontal scaling, each on its own channel:

| Server                   | Mount      | Purpose                              |
| ------------------------ | ---------- | ------------------------------------ |
| `socket_handler`         | `/ws`      | Scan progress, general notifications |
| `netplay_socket_handler` | `/netplay` | Netplay room management              |

Netplay clients may be anonymous guests and name their own rooms, so they must never see the `user:{id}` or `admin` rooms. `socket_handler.emit_to_user(user_id, event, payload)` pushes to one user's open tabs from the web process or a worker. Registered devices connect to the `/devices` namespace of the `/ws` server (see [Devices](#devices-namespace-devices-on-wssocketio)); rooms and events are per namespace, so the web UI never receives device traffic.

### 7.9 Notifications (`handler/notification_handler.py`)

Persistent per-user notifications, kept until dismissed and pushed live to the user's `user:{id}` socket room. From backend code, web process or worker alike:

```python
await notify(user.id, NotificationKind.SCAN_COMPLETED, NotificationLevel.SUCCESS, stats)
await notify_admins("custom", NotificationLevel.WARNING, title="Disk almost full")
```

A `NotificationKind` is translated by the client from `data`; a new one needs a describer in `frontend/src/utils/notifications.ts` and locale keys. Until then, or for a one-off, pass any other kind with `title`/`body`/`link`/`icon`. Both helpers log and swallow failures, so a job never fails over reporting itself.

A client may send its own notification through `POST /api/notifications`, carrying `title`, `body`, `icon` (`mdi-*`) and `link`, which must be a path inside RomM. RomM's own `kind`s are reserved; any other (`custom`, `argosy.sync_done`) is shown as sent.

A task reports its success from `run_task_by_name`. Its failure is reported by `report_task_failure`, an exception handler `RomMWorker` installs, so a timeout, a killed work horse or a dead worker notifies too, for cron runs as well as manual ones. The handler can run in the worker parent, so it enqueues `notify_task_failure` on the default queue rather than loading the notification stack there.

### 7.10 Notification Channels (`handler/notification_channels/`)

Each user forwards their own notifications to other services. A channel is one of three types:

- `apprise`: any of the 100+ services [Apprise](https://github.com/caronc/apprise#supported-notifications) reaches, set up through that service's own fields. **Admins only**, since Apprise opens its own connections, past the SSRF guard. The owner's role is checked again at every delivery, so a demoted admin's channel fails until it turns off.
- `webhook`: RomM's own JSON payload (below), POSTed to an http(s) URL.
- `email`: a plain-text email over the server's SMTP, to an address confirmed with a 6-digit code first.

A channel filters by minimum level and by topic (`scans`, `tasks`, `streaming`, `account`, `custom`); every stored notification that passes goes out in its own RQ job, retried at 30 s, 2 min and 10 min. A channel that fails 10 deliveries in a row turns itself off and tells its owner.

The Apprise catalog comes from Apprise's own plugin details: URL tokens become fields, options become advanced fields, and a field is required only when every URL template of its service needs it. A channel stores its service and fields, sealed, and each delivery builds the URL from the template those fields fill. Schemas that act on the host (`syslog`, `dbus`, `windows`...), FCM, and options Apprise reads from a local file are not offered. Apprise follows no redirects and doesn't retry, and its timeouts are capped at 10 s to connect and 15 s to read. The API returns the fields that aren't secret and names the secrets; on edit, a secret left out stays and an empty one goes, but a kept secret never follows the channel to another destination.

Only an admin's webhooks may reach private addresses; everyone else's go through the SSRF guard (`utils/ssrf.py`). A webhook delivery gets 15 s in all, and only the start of a refusal's body is read. Links are absolute only when `ROMM_BASE_URL` is shareable.

```json
{
  "event": "notification",
  "id": 42,
  "kind": "scan_completed",
  "level": "success",
  "title": "Scan completed",
  "body": "3 new games",
  "url": "https://romm.example.com/scan",
  "data": { "new_roms": 3 },
  "actor": null,
  "created_at": "2026-09-23T12:00:00+00:00"
}
```

With a secret, a webhook adds `X-RomM-Signature: sha256=<hex HMAC-SHA256 of the body>`. Email needs `SMTP_HOST` and `SMTP_FROM`; the heartbeat's `NOTIFICATIONS.EMAIL_ENABLED` says whether it's set up. Channel configs are sealed with a key derived from `ROMM_AUTH_SECRET_KEY`, so rotating it means entering their URLs and secrets again.

---

## 8. External Integrations (Adapters)

`adapters/services/` holds one HTTP client per external service (IGDB, MobyGames, ScreenScraper, SteamGridDB, RetroAchievements and others), each wrapping that provider's auth, rate limits and response types. The matching handler in `handler/metadata/` turns its answers into RomM's fields. A provider is active when its keys are set or its `*_API_ENABLED` toggle is on (see `env.template`).

Static indexes (MAME, ScummVM, console serial codes, known BIOS hashes) ship as JSON fixtures under `handler/metadata/fixtures/` and `models/fixtures/` and are loaded into Redis at startup.

---

## 9. Real-Time Communication (WebSockets)

```text
Client  ←──Socket.IO──→  FastAPI (python-socketio)  ←──Redis PubSub──→  Workers
```

### Scan Progress (`/ws`)

A scan emits `scan:update_stats` with its counts after each platform or rom, `scan:log` for log lines, and `scan:stop` when it completes or is cancelled.

### Notifications (`/ws`)

Sent to the user's own `user:{id}` room: `notifications:new` when one is stored, and `notifications:read` / `notifications:dismissed` when another tab changes some, so every tab stays in step.

### Netplay (`/netplay`)

Rooms are authorized per ROM. A socket is identified once, at `connect`, from its
session cookie, and is closed when that login session is revoked. The identity is
reloaded on every gated event so a disabled account loses access without waiting
for a reconnect. `open-room` requires a logged-in user with `roms.read` who can
see the ROM being played. `join-room` into a room with a password requires that
password (sent as `password` beside `extra`), which is the guest invite path; a
room without one requires the same access as `open-room`. `GET /api/netplay/list`
requires `roms.read` and 404s for a ROM the caller cannot see, through the same
guard the other ROM endpoints use. WebRTC signals relay only between peers of the
same room, and leaving the room ends that relay. Room state lives in Redis.

### Devices (namespace `/devices` on `/ws/socket.io`)

Only a registered device connects, with a client token bound to it
(`ClientToken.device_id`) that holds `devices.read`, sent as `token` in the
handshake auth payload or as an `Authorization: Bearer` header. A browser
session is never accepted, and every connection is refused while
`DEVICE_INSTALL_ENABLED` is off. Connecting bumps the token's `last_used_at`
and the device's `last_seen`; capabilities travel over the device REST
endpoints. The socket joins `device:{device_id}` in the namespace and is
closed when its token is deleted, regenerated or re-paired, its device or
owner is deleted, its owner is disabled, or its owner's permissions change,
and within 30 seconds of the token's `expires_at`. Each open socket refreshes
`device_presence:{device_id}` and its token's `device_token_sockets:{id}` every
30 seconds. The presence key lapses 90 seconds after the last refresh and loses
the socket on disconnect. A device that polls claim instead sets
`device_claim_presence:{device_id}` on each claim, which lapses after the same
90 seconds. `GET /api/devices/online` lists the caller's devices with either key
live (404 while `DEVICE_INSTALL_ENABLED` is off). The per-token socket sets exist
only to close sockets on revocation and never answer presence.

| Event               | Direction              | Description                                                |
| ------------------- | ---------------------- | ---------------------------------------------------------- |
| `install:queued`    | Server to device       | `{id, rom_id}`: an install request is waiting              |
| `install:cancelled` | Server to device       | `{id, rom_id}`: the owner cancelled a pending or taken one |
| `install:updated`   | Server to owner on `/` | An `InstallRequestSchema` changed status                   |

An install request exists only while it is `pending` or `taken`. It lives in
Redis as JSON under `install:req:{id}`, indexed by `install:device:{device_id}`
and `install:rom:{user_id}:{rom_id}`;
`install:active:{user_id}:{device_id}:{rom_id}` names the one live request per
rom and device, so a second create returns it. A live request expires
`DEVICE_INSTALL_REQUEST_TTL_DAYS` after its last change (never when that is 0),
which bounds an abandoned one. A request carries the rom's game, update and DLC
files on disk; a rom without any, a rom on a platform in
`DEVICE_INSTALL_EXCLUDED_PLATFORM_SLUGS`, or a device whose `capabilities` lack
`remote_install`, is a 400.

The owner creates requests (`POST /api/devices/{device_id}/installs`), reads a
rom's live ones (`GET /api/roms/{id}/installs`) and cancels one still pending or
taken (`DELETE /api/devices/{device_id}/installs/{id}`).

Every client drains its queue through `POST
/api/devices/{device_id}/installs/claim`, which moves all pending requests to
`taken` in one Redis transaction and returns every request the device holds
taken, so a device that lost a claim's response gets them back on its next
claim. Only newly taken requests emit `install:updated`. The socket is optional: a
client holding it claims on `install:queued`, and one that cannot hold a socket
polls claim on its own schedule. Only a client token bound to the device claims
or reports. A report (`PUT /api/devices/{device_id}/installs/{id}`) names
`done`, `already_installed` or `failed` for a taken request.

Each operation checks the status it needs and writes inside one Redis `WATCH`
transaction: claim takes only pending requests, a report needs a taken one, and
a cancel a pending or taken one. A request in another live status is a 409.
A report or a cancel ends the request: the server emits `install:updated` with
the final status, deletes the request, its index entries and its
`install:active` key in the same transaction, and for a report notifies the
owner (`device_install_completed` or `device_install_failed`, with the reason).
A report or cancel for a request that no longer exists is a 404, so a device
treats a 404 on a retried report as already handled, and a cancel racing a
report cannot both succeed. A cancel racing a claim either keeps the request
out of that claim or cancels it after the claim took it. Deleting a device, or
its owner, drops the device's live requests.

---

## 10. Background Tasks & Scheduling

### Job Queue System

Jobs run on RQ (`handler/redis_handler.py`):

| Queue             | Use Case                                       |
| ----------------- | ---------------------------------------------- |
| `high_prio_queue` | Urgent operations                              |
| `default_queue`   | Standard background work                       |
| `low_prio_queue`  | Cleanups, conversions, metadata refreshes      |
| `scan_queue`      | Library scans, consumed by a worker of its own |
| `streaming_queue` | Reaper, exit saves; worker if streaming is on  |

### Scheduled Tasks

Declared in `tasks/registry.py` and registered with RQ's cron scheduler by
`tasks/cron_config.py`, which the `rq cron` process loads at start. The registry
holds each task's `TaskSpec` (title, schedule, queue, timeout) and the dotted
path to the `Task` that runs it, which `get_task` imports only when a job runs.
The scheduler, the tasks API and the worker's failure reporting read specs
alone, so they never load task code. A task is registered only when it is
enabled and has a cron string, so turning one off is a restart rather than an
unschedule. Each task's toggle and default schedule are in its spec and in
`env.template`. Delayed jobs, which is how the filesystem watcher defers a
rescan, are released by the worker itself (`--with-scheduler`).

Everything is registered on `low_prio_queue`. A scan is registered as a dispatch
job that enqueues the real scan onto `scan_queue`, because cron can attach no
failure callback and a scan needs one to report a worker that died mid-scan.

### Manual Tasks

Triggered via `POST /api/tasks/run/{task_name}`, which enqueues on
`low_prio_queue` and answers 503 when no live worker is listening on it. A spec
marked `destructive` asks for a typed confirmation before the UI runs it, and
one marked `single_instance` answers 409 while a job of it is queued or running.

`convert_library` is both, and runs only with `ROM_CONVERTO_ENABLED` set. It
only converts losslessly (no xiso) and only identified ROMs, since a converted
file no longer hash-matches a DAT. It stages each output under a `.romm_tmp_`
directory beside the ROM, deletes the originals (and a cue's tracks) once the
output is in place, rewrites `.m3u` entries in folder ROMs, and refreshes the
ROM's files, so the ROM keeps its id, saves and collections.

`cleanup_orphaned_resources` skips the cleanup when the database reports no
platforms at all while artwork is still on disk, since that usually means the
database is unavailable rather than the library being empty. Pass
`{"force": true}` as the request body to clean up a genuinely emptied library.

### Filesystem Watcher

`watcher.py` uses `watchfiles` to monitor the library. When
`ENABLE_RESCAN_ON_FILESYSTEM_CHANGE` is on, it schedules a rescan after
`RESCAN_ON_FILESYSTEM_CHANGE_DELAY`.

---

## 11. File System Management

### Directory Layout

```text
{ROMM_BASE_PATH}/                    # Default: /romm
├── library/                         # ROM files, organized by platform (layout set in config.yml)
│   └── {platform_slug}/
│       ├── roms/
│       └── bios/                    # Firmware/BIOS files
│
├── resources/                       # Cached metadata assets, per rom
│   └── roms/{rom_id}/
│
├── assets/                          # User-generated assets
│   └── users/{user_id}/{rom_id}/
│       ├── saves/
│       ├── states/
│       └── screenshots/
│
└── config/
    └── config.yml                   # YAML configuration
```

### File Serving

In production, endpoints answer with an nginx `X-Accel-Redirect` header (`utils/nginx.py`), so nginx serves the file from disk without passing bytes through Python. With `DEV_MODE=true` they answer with a direct `FileResponse`.

### Hash Calculation

CRC32, MD5 and SHA1 identify ROMs and verify BIOS files; MD5 also deduplicates saves, and the RetroAchievements hash is computed per platform. Hashing can be turned off with `skip_hash_calculation` in `config.yml`.

Alongside hashing, scans extract platform-native title IDs from ROM binaries via
the optional `sigil` binding (Switch, PlayStation, Nintendo, Xbox and Dreamcast
families). The feature no-ops when the binding is absent, and can be turned off
with `skip_title_id_extraction`.

---

## 12. Caching (Redis)

`handler/redis_handler.py` holds a sync client (`redis_client`, decoding responses) for cache queries and session lookups, and an async one (`async_cache`). Tests run against FakeRedis.

Redis holds login sessions, one-time token JTIs, socket and device presence sets, install requests, upload sessions, netplay rooms, the startup fixture indexes and query caches. Each key's prefix and TTL are set where it is written; grep for the prefix to find its owner.

---

## 13. Configuration, Errors & Logging

**Configuration.** Environment variables are read once in `config/__init__.py`; `env.template` lists them with their defaults. `config.yml` is managed by `ConfigManager` (`config/config_manager.py`, a singleton) which reads, validates and writes it; `examples/config.example.yml` shows every key.

**Errors.** Domain exceptions live in `exceptions/`, grouped by area (auth, config, database, endpoint, filesystem, socket, task). A hidden entity raises the same not-found exception as a missing one.

**Logging.** The `romm` logger writes `[LEVEL]: [RomM][module] [timestamp] message`, at the level `LOGLEVEL` sets. `FORCE_COLOR` and `NO_COLOR` control ANSI colors. Sentry is enabled by `SENTRY_DSN`, with releases tagged `romm@{version}`.

---

## 14. Testing

- `pytest.ini` turns on async mode, points at the `romm_test` database, and sets mock API keys with OIDC off.
- Tests mirror the backend tree under `tests/` (`backend/<area>/x.py` → `tests/<area>/test_x.py`).
- External API tests replay VCR cassettes, so they run without network.
- Endpoint tests use FastAPI's `TestClient`; Redis is FakeRedis.
- `romm_test/` holds a small library, configs and user asset fixtures.

See `AGENTS.md` for which tests to run locally and for the per-worktree test database.

---

## Appendix: Key Design Patterns

| Pattern                     | Where                                | Purpose                           |
| --------------------------- | ------------------------------------ | --------------------------------- |
| **Three-tier architecture** | Endpoints → Handlers → Models        | Separation of concerns            |
| **Singleton**               | `ConfigManager`                      | Single config instance            |
| **Adapter pattern**         | `adapters/services/`                 | Normalize external APIs           |
| **Decorator pattern**       | `@protected_route`, `@begin_session` | Cross-cutting concerns            |
| **Context variables**       | `utils/context.py`                   | Request-scoped state (async-safe) |
| **Repository pattern**      | `handler/database/`                  | Encapsulate data access           |
| **Observer pattern**        | Socket.IO events                     | Real-time updates                 |
| **Priority queues**         | RQ queues by priority and purpose    | Task scheduling                   |
| **Chunked upload**          | `endpoints/roms/upload.py`           | Large file handling               |
| **X-Accel-Redirect**        | `utils/nginx.py`                     | Efficient file serving            |
