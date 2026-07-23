# Proposal: Hosted RomM for Save Sync Only

Status: design draft
Scope: backend + deployment; no code changes yet

Decisions already made:

- **We are hosting this.** Multi-tenant hardening is on the critical path, not
  an optional follow-up.
- **The management UI is a micro-UI built outside this repo.** It consumes this
  repo's OpenAPI schema and public API only. No new frontend work lands in
  `frontend/`.

## 1. The idea

Users keep asking for a hosted RomM that acts purely as a transparent save-sync
layer: no ROM files anywhere, an account, a device list, and save/state storage
that syncs between clients (Argosy, Grout, the Playnite plugin, RetroArch Sync,
and friends). Think "Syncthing for retro saves, with RomM's protocol".

Two questions are explored here:

1. What has to change in RomM for a fileless, save-sync-only deployment to work?
2. What stays in this repo vs. what lives outside it?

## 2. What already works today

The exploration turned out better than expected. Most of the machinery a
save-sync service needs already exists and does not depend on ROM binaries:

- **The app boots with an empty or missing library.** All base directories are
  auto-created (`handler/filesystem/base_handler.py:154`), and an empty library
  is bootstrapped rather than treated as an error
  (`handler/filesystem/platforms_handler.py:88`). The only hard boot
  requirements are `ROMM_AUTH_SECRET_KEY`, DB credentials, and Redis.
- **Asset storage never touches ROM files.** Saves/states/screenshots live
  under `assets/users/<user>/<kind>/<platform_fs_slug>/<rom_id>/<emulator>/`
  (`handler/filesystem/assets_handler.py:97`). Paths are derived from scalars
  (user, platform slug, rom id, emulator), not from the ROM binary.
- **The whole sync path is ROM-file-agnostic, verified end to end.** Save/state
  uploads check only that the `Rom` row exists in the DB
  (`endpoints/saves.py:176`, `endpoints/states.py:45`); asset downloads check
  only that the asset file itself exists; `/api/sync/negotiate` is pure DB and
  pairs on `(rom_id, slot)` (`endpoints/sync.py:106`). A `Rom` row with no
  backing file breaks nothing in this path, so virtual roms can be DB-only, no
  placeholder files needed.
- **The client API contract is already there and is what the official clients
  speak:**
  - `POST/GET /api/saves`, `/api/states` with multipart upload, slots,
    datetime-tagged slot history, autocleanup, and MD5 `content_hash` dedup
    (`endpoints/saves.py`).
  - Device registration, the RFC-8628-style pairing flow
    (`endpoints/device_auth.py`), and long-lived `rmm_` client tokens
    (`handler/auth/hybrid_auth.py:54`).
  - Per-device sync bookkeeping via `device_save_sync` and 409 conflict guards
    on stale uploads (`endpoints/saves.py:209`).
- **Saves are already per-user.** Physical namespacing per user on disk, every
  query scoped to `request.user.id`, cross-user access only via the explicit
  `is_public` opt-in (`endpoints/saves.py:466`).
- **Metadata providers are optional and lazy.** Every handler guards network
  calls with `is_enabled()`; a deployment with zero provider keys works.
- **The backend is already headless.** FastAPI serves only `/api`, `/ws`, and
  `/netplay`; the SPA is served by nginx in production. Running without the
  bundled frontend is a deployment choice, not a code change, which is exactly
  what the external micro-UI needs.

In other words: nothing crashes with zero ROM files, and the sync protocol
itself is file-agnostic.

## 3. The gaps

### 3.1 The hard one: game identity without files

Every asset row requires a `rom_id` (non-nullable FK, `models/assets.py:66`),
and every upload endpoint 404s if the `Rom` row does not exist. That is fine;
the problem is upstream:

**`Rom` rows are only ever created by the filesystem scanner.**
`db_rom_handler.add_rom` is called exclusively from the scan flow
(`endpoints/sockets/scan.py:330`, `handler/scan_handler.py:463`). There is no
`POST /api/roms`; the ROM upload endpoint writes bytes to disk and relies on a
subsequent scan. So a fileless deployment can never mint the `Rom` rows that
saves attach to.

Creating roms without files has two mechanical constraints:

- `Rom` has six non-nullable filesystem columns (`fs_name`, `fs_name_no_tags`,
  `fs_name_no_ext`, `fs_extension`, `fs_path`, `fs_size_bytes`) that must be
  synthesized from the resolve payload (`models/rom.py:326`).
- A unique index on `(platform_id, fs_name)` (`models/rom.py:295`) means
  synthetic names must be unique per platform. This is a feature: it is the
  race-safety mechanism for a get-or-create endpoint.

### 3.2 Secondary issues that follow from "no files"

- `Platform` creation works fileless in practice (`POST /api/platforms` mkdirs
  an empty folder and resolves metadata by slug, `endpoints/platform.py:45`),
  but the mkdir side effect is accidental, not designed.
- The `cleanup_missing_roms` task deletes every rom with
  `missing_from_fs=True` (`tasks/manual/cleanup_missing_roms.py:58`). Reusing
  that flag to represent virtual roms would make one admin click destroy all
  save anchors. Virtual roms need their own marker.
- ROM download endpoints go through nginx `X-Accel-Redirect` to local disk and
  would fail for fileless roms; they should be gated off entirely in sync-only
  mode.

### 3.3 Hosted-service gaps

- No per-user storage quotas exist anywhere (`models/user.py` has no quota
  column).
- Inbound rate limiting exists only as per-IP Redis limiters on the device-auth
  flow (`utils/device_auth.py:26`) and the client-token exchange
  (`utils/client_tokens.py:59`). Nothing app-wide.
- CORS is configured as `allow_origins=["*"]` with `allow_credentials=True`
  (`main.py:112`). Browsers refuse to send credentials to a literal `*`, so a
  cross-origin micro-UI using cookie sessions cannot work against today's
  config. The hosted instance needs explicit allowed origins (or the micro-UI
  authenticates with tokens instead of cookies; see open questions).
- Storage is hardcoded local filesystem behind `FSHandler`; there is no object
  storage abstraction. Asset downloads already stream through Starlette
  `FileResponse` rather than nginx redirects, which keeps a future S3 swap
  contained.

## 4. Proposed design

### 4.1 A `SYNC_ONLY_MODE` deployment flag

A single env flag (name TBD, e.g. `ROMM_SYNC_ONLY=true`) that turns a normal
RomM instance into a fileless sync server:

- Do not register ROM-centric routers, or return 404/disabled from them: rom
  download/upload, feeds, firmware, export, netplay, EmulatorJS config.
- Do not schedule filesystem-driven tasks: `scan_library`, the filesystem
  watcher, `convert_images_to_webp`.
- Make the platform-creation mkdir side effect an explicit no-op.
- Expose the mode in the heartbeat endpoint so clients and the micro-UI can
  adapt.

Virtual roms are DB-only rows; no placeholder files are generated (verified
unnecessary in section 2). The bundled frontend needs no gating: the hosted
deployment simply does not ship the SPA, and the micro-UI lives in its own
repo. For self-hosters who flip the flag on a standard image, the existing UI
already degrades to an empty gallery; no dedicated in-repo UI work is planned.

Kept as-is: auth (sessions, OIDC, client tokens, device pairing), users,
devices, saves/states/screenshots, `/api/sync`, play sessions, stats (scoped
to assets).

### 4.2 Game identity: a get-or-create "resolve" endpoint

The crux. Clients need to turn "the game I am holding a save for" into a
`rom_id`, consistently across devices, without the server ever seeing the ROM.

Proposal: `POST /api/roms/resolve` (scope discussion in open questions),
available in all modes, not just sync-only:

```jsonc
{
  "platform_slug": "gba", // required, canonical slug
  "fs_name": "Metroid Fusion (USA).gba", // required, the client-side filename
  "md5_hash": "...", // optional but strongly encouraged
  "crc_hash": "...", // optional
  "sha1_hash": "...", // optional
  "name": "Metroid Fusion", // optional display name hint
}
```

Server behavior:

1. Get-or-create the `Platform` by slug.
2. Match an existing `Rom` on that platform: first by hash (md5/sha1/crc),
   then by normalized `fs_name`. Return it if found. This also makes the
   endpoint useful for regular installs: a client can resolve against a real
   scanned library without listing and fuzzy-matching roms client-side, which
   is what clients do today.
3. Otherwise create a virtual rom row: a new `is_virtual` boolean column (one
   small migration), `missing_from_fs=False`, hashes stored if provided, and
   the non-nullable `fs_*` columns synthesized from the payload. `fs_name`
   gets a deterministic uniquifying suffix (e.g. a hash prefix) to satisfy the
   `(platform_id, fs_name)` unique index; `fs_size_bytes=0`; `fs_path` is a
   synthetic prefix that never collides with the real library tree.
4. Enqueue metadata identification by name and hash through the existing scan
   handler machinery (providers are optional; on the hosted instance this is
   what makes the micro-UI's library view pretty with covers).

Identity notes:

- Hashes are the only reliable cross-device key. Two devices with the same
  dump resolve to the same row without any name normalization guesswork.
  Filename matching is the fallback for platforms where clients cannot hash
  (Switch, PS3+) and for save files that arrive without their ROM context.
- The endpoint must be idempotent and race-safe: insert, catch the unique
  violation on `(platform_id, fs_name)`, re-fetch. A client will call it once
  per game in a library dump.
- `cleanup_missing_roms` must exclude `is_virtual` rows unconditionally, in
  every mode, so an admin click can never destroy save anchors.
- Virtual roms deduplicate lazily: the scanner already reassociates moved
  files to existing rows by hash (`endpoints/sockets/scan.py:301`); extending
  that to claim a matching virtual row (clearing `is_virtual`) merges virtual
  and real libraries without duplicates.

Client impact: one new call. Existing flows keep working; clients that already
resolve rom ids by listing `/api/roms` continue to work because virtual roms
are ordinary roms.

### 4.3 Multi-tenant hardening (critical path for the hosted instance)

| Concern               | Today                                                               | Change                                                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Storage quotas        | None (no quota column on users)                                     | Per-user `storage_quota_bytes` (users table or config), enforced in asset upload paths; usage = sum of `file_size_bytes` per user, cached. Saves are small; states can be tens of MB; also cap single-file size. |
| Rate limiting         | Per-IP Redis limiters on device-auth and client-token exchange only | Generalize the existing limiter pattern into middleware for auth and upload endpoints.                                                                                                                           |
| Registration          | First-admin bootstrap + invite links only                           | Either OIDC-only signup (provider handles abuse) or an open-registration flag with email verification. Invite links already exist for a closed beta.                                                             |
| Cross-origin micro-UI | `allow_origins=["*"]` + credentials (broken for cookie auth)        | Configurable explicit allowed origins; pick the micro-UI auth model (open question).                                                                                                                             |
| Abuse of stored bytes | Saves served as `application/octet-stream` attachments already      | Keep; add per-file size caps and content-length enforcement on multipart uploads.                                                                                                                                |
| Horizontal scale      | Socket.IO and sessions already Redis-backed                         | App tier scales out today; the filesystem is the sticky part (see 4.4).                                                                                                                                          |
| Blast radius          | Admin endpoints, tasks, config writes                               | Hosted operator holds admin; regular users get the standard USER role, which already cannot touch tasks/config/users.                                                                                            |

### 4.4 Storage backend

Phase 1 can ship on local disk plus volume backups; save data volume is tiny
compared to ROM libraries (a heavy user is megabytes, not terabytes).

Phase 2, if the hosted service grows: introduce a storage interface behind
`FSHandler` (local + S3 implementations) for the assets tree only. Asset
downloads already stream through Starlette `FileResponse` rather than nginx
redirects, so S3-backed serving (or presigned redirects) is a contained
change. The ROM library path never needs this in sync-only mode.

## 5. What lives where

The "mode vs. spin-off" question is settled by the two decisions up top:

- **Backend: everything in `rommapp/romm` behind the mode flag.** The sync
  protocol, auth, device pairing, and asset model are the product; they
  already live here and the official clients track this repo's OpenAPI schema.
  Extracting a separate server would fork the protocol: every change to
  `/api/saves` or `/api/sync` would have to land twice, and clients would face
  two drifting servers claiming the same API. The resolve endpoint and
  quota/rate-limit work benefit normal self-hosted installs too.
- **Micro-UI: separate repo.** It consumes the backend's OpenAPI schema (same
  generation pipeline the bundled frontend uses) and speaks only the public
  API: account, devices, per-game save browser, client tokens, quota meter.
  Nothing in `frontend/` changes; v1 stays frozen and v2 work is unaffected.
- **Infra: separate repo.** Compose/helm for the hosted stack:
  `ROMM_SYNC_ONLY=true`, explicit CORS origins, OIDC config, backup jobs,
  monitoring. Infra-as-code stays out of the app repo.

One protocol implementation, three repos, each with its own release cadence.

## 6. Phased plan

Phase 1, backend enablers (small/medium effort, all in this repo):

1. `is_virtual` column on `roms` + migration; `cleanup_missing_roms` excludes
   virtual roms unconditionally.
2. `POST /api/roms/resolve` (get-or-create, hash-first matching, unique-index
   race safety).
3. `SYNC_ONLY_MODE` flag: router gating, task gating, no-op platform mkdir,
   heartbeat exposes the mode.
4. Configurable CORS allowed origins (prerequisite for the external UI).
5. Tests: resolve endpoint (match by hash, by name, create, race), sync-only
   route gating, cleanup safety.

Phase 2, hosted beta (medium effort, spans repos):

6. Per-user quotas + per-file size caps.
7. Rate-limit middleware on auth + upload routes.
8. OIDC-only or invite-based signup for the hosted instance.
9. Hosted deployment stack in the infra repo: backups, monitoring.
10. Micro-UI v1 in its own repo against the OpenAPI schema.

Phase 3, scale (as needed):

11. Storage interface + S3 backend for the assets tree.
12. Virtual-to-real rom merging in the scanner (claim matching virtual rows
    on scan instead of creating duplicates).

## 7. Open questions

- Scopes: should `resolve` require `roms.write`, or should a narrower
  `roms.resolve`-style grant exist so sync clients do not get general rom
  write access? Today's client tokens carry coarse scopes.
- Micro-UI auth model: cookie sessions (requires the UI on a sibling
  subdomain plus explicit CORS origins) or token-based auth in the browser?
  This decides how much of the CORS work in phase 1 is needed.
- Hash coverage in clients: which of Argosy/Grout/Playnite/RetroArch Sync can
  cheaply provide md5/crc at resolve time? Filename-only resolution works but
  weakens cross-device identity for renamed files.
- Do screenshots count against the user storage quota, or only saves/states?
- Should the hosted instance disable the community `is_public` save sharing,
  or is it part of the product?
