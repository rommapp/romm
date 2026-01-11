# SFU Authentication + Netplay Identity Design (RoMM)

Date: 2026-01-09

## 1) Summary

We want a mediasoup-based SFU service (Node.js) to:

1. **Authorize** a client to connect.
2. **Authenticate** the client as a specific RoMM user.
3. Retrieve a stable **Netplay Username** for that user to avoid client-side name prompts and prevent impersonation.
4. Maintain SFU-owned state (rooms, banlists, room behaviors, ROM/core metadata) in Redis.
5. Support future federation via **Trusted Sites** using public/private keys.

Key constraint: SFU should **not** have broad access to RoMM’s Redis data (sessions, user data, etc.). It should only read/write what it needs.

The recommended approach is to expose only a **dedicated Redis keyspace** to SFU (`sfu:*`) and place user identity + authorization material there.

---

## 2) Existing RoMM Auth + Redis Observations

Relevant current patterns:

- **Session auth is Redis-backed**:

  - Cookie `romm_session=<session_id>`.
  - Session payload stored at `session:<session_id>` (JSON, includes `iss` + `sub`).
  - Per-user set `user_sessions:<username>` tracks active session ids.

- **JWT is used already** (HS256 via `ROMM_AUTH_SECRET_KEY`):

  - OAuth bearer tokens: `iss=romm:oauth`, `type=access|refresh` (no Redis revocation).
  - Password reset / invite links: JWT includes `jti`; Redis `SETEX <prefix>:<jti> "valid"` used as a one-time gate.

- **Socket.io uses Redis manager for scaling**, not for auth decisions.
- **Netplay sockets currently trust client-supplied `player_name` and `userid/playerId`**.

This design borrows the already-established “JWT + Redis JTI gate” pattern, but isolates SFU access to `sfu:*`.

---

## 3) Goals and Non-goals

### Goals

- SFU can validate a client quickly: **JWT verify + Redis read**.
- SFU can determine:
  - authenticated RoMM user id (username; `sub`)
  - stable `netplay_username`
  - optional scopes/roles
- RoMM can revoke SFU tokens quickly (short TTL and/or allowlist deletion).
- SFU has strict Redis least-privilege via ACL and key patterns.

### Non-goals (for now)

- Full multi-tenant identity across different RoMM instances (handled later via federation).
- Replacing RoMM’s existing auth (session/OAuth). This is additive.

---

## 4) Threat Model (Practical)

Primary threats:

- **Impersonation** by forging user identifiers in signaling.
- **Token replay** if a token leaks (logs, query strings, referers).
- **Privilege escalation** if SFU can read sensitive Redis keys.
- **Cross-site federation spoofing** without proper signature validation.

Mitigations:

- JWT signature verification (HS256 today; can migrate to asymmetric later).
- Short-lived SFU tokens (e.g. 60–180 seconds).
- Redis allowlist keyed by JTI to allow fast revocation and to prevent accepting arbitrary signed tokens if needed.
- Keep SFU Redis access limited to `sfu:*`.
- Avoid query parameters for tokens where possible; prefer `Authorization: Bearer`.

---

## 5) Redis Access Control (Least Privilege)

### 5.1 Separate Redis user for SFU

Create a Redis ACL user dedicated to the SFU process.

Practical shortcut: this repo includes a ready-to-copy ACL example with a
`romm` admin user and an `sfu` least-privilege user in
[examples/redis/users.acl.example](examples/redis/users.acl.example).

Note: RoMM background workers (RQ) use Redis Pub/Sub channels (e.g. `rq:pubsub:*`).
In Redis ACL, channel permissions are controlled by `&` patterns, separate from key
patterns (`~`). The `romm` user must be granted channel access (the example uses `&*`).

Netplay/SFU deployments in RomM require Redis ACL users (no unauthenticated
default user). RomM runs with the `romm` user, while the SFU uses a dedicated
restricted user via `SFU_AUTH_REDIS_URL`.

Principles:

- Restrict keys: `~sfu:*` only.
- Restrict commands: only what’s needed for the chosen data structures.
- Prefer disabling broad discovery commands (`KEYS`), scripting (`EVAL`), config (`CONFIG`), flush (`FLUSH*`).

Example (adjust per Redis version and your command choices):

- Enable: `GET`, `SET`, `SETEX`, `DEL`, `EXISTS`, `EXPIRE`, `TTL`
- Hash: `HGET`, `HSET`, `HGETALL`, `HEXISTS`, `HDEL`
- Set: `SADD`, `SREM`, `SMEMBERS`, `SISMEMBER`

If you need scanning:

- Prefer a maintained index key (e.g. `sfu:rooms:index`) over `SCAN`.

### 5.2 Data segregation

All SFU-owned state must live under `sfu:*`. SFU must not access:

- `session:*`
- `user_sessions:*`
- `netplay:rooms`
- any DB credentials or other config keys

---

## 6) Token Strategy (RoMM → SFU)

### 6.1 Token type

Use a **short-lived JWT** that proves RoMM issued authorization for SFU connection.

- Algorithm: HS256
- Signing key: `ROMM_AUTH_SECRET_KEY` (initially)
  - Future: dedicated `SFU_AUTH_SECRET_KEY` or asymmetric signing.

### 6.2 JWT Claims

Required claims:

- `iss`: `romm:sfu`
- `sub`: `<romm_username>`
- `iat`: issued-at (unix seconds)
- `exp`: expiry (unix seconds)
- `jti`: random unique token id

Optional claims:

- `scopes`: list or space-separated string (e.g. `sfu:connect`, `sfu:publish`, `sfu:subscribe`)
- `room`: if issuing room-bound tokens
- `aud`: `romm:sfu` or SFU service id (recommended)

### 6.3 Redis allowlist entry (authoritative)

When RoMM mints the JWT, it creates a Redis record under `sfu:*`:

- Key: `sfu:auth:jti:<jti>`
- Type: hash
- TTL: same as token TTL (or slightly longer)

Fields (minimum):

- `sub`: `<romm_username>`
- `netplay_username`: `<stable_display_name>`
- `exp`: `<unix seconds>` (optional; TTL already enforces)
- `scopes`: `<string>` (optional)
- `minted_at`: `<unix seconds>` (optional)
- `source`: `session|oauth` (optional)

This ensures SFU can read only what it needs without requiring access to RoMM sessions or database.

### 6.4 Validation in SFU

On SFU connection attempt:

1. Extract JWT from `Authorization: Bearer <token>` (preferred).
2. Verify:
   - signature using `ROMM_AUTH_SECRET_KEY`
   - `iss == romm:sfu`
   - `exp` not expired
   - optional `aud` matches
3. Read Redis:
   - `HGETALL sfu:auth:jti:<jti>`
   - Reject if missing.
4. Cross-check:
   - Redis `sub` equals JWT `sub`.
   - optional scope checks.
5. Use `netplay_username` from Redis as the authoritative player name.

Optional: one-time use

- After successful validation, SFU can `DEL sfu:auth:jti:<jti>` to prevent replays.
- If you do this, clients must request a fresh token on reconnect.

---

## 7) Netplay Username

### 7.1 Where it lives

RoMM currently does not have a dedicated `netplay_username` column on the User model.

We need to choose where the authoritative value will come from:

Option A (fastest integration):

- Store it in `users.ui_settings` (JSON) as something like `ui_settings.netplay.username`.

Option B (clean DB model):

- Add a column later (e.g. `users.netplay_username`) with constraints.

Regardless of where RoMM stores it, **SFU only reads it from `sfu:auth:jti:<jti>`**, never directly from user DB or other Redis keys.

### 7.2 Validation rules (recommended)

RoMM should enforce:

- length (e.g. 3–20)
- allowed chars (e.g. letters, digits, `_-. `)
- disallow leading/trailing whitespace

SFU should treat it as display-only, not as a security identifier.

---

## 8) SFU-owned Room Metadata in Redis

All SFU room state lives under `sfu:rooms:*`.

### 8.1 Room core

- `sfu:rooms:<room_id>` (hash)
  - `owner_sub`
  - `room_type` (e.g. `public|private|tournament|friends`)
  - `core` (emulator core name/version)
  - `rom_id` (RoMM rom id or external id)
  - `game_name` (optional)
  - `created_at`, `updated_at`

TTL strategy:

- Either no TTL + cleanup job, or TTL with refresh on activity.

### 8.2 Players

- `sfu:rooms:<room_id>:players` (set)
  - members are `sub` or `participant_id`

Optional per-player metadata:

- `sfu:rooms:<room_id>:player:<sub>` (hash)
  - `joined_at`, `role`, etc.

### 8.3 Banlists

Room banlist:

- `sfu:ban:room:<room_id>` (set)
  - contains `sub` values

Optional:

- `sfu:ban:room:<room_id>:meta` (hash) or per-user keys for reason/expiry.

Global banlist (optional):

- `sfu:ban:global` (set)

### 8.4 Index keys (avoid SCAN)

- `sfu:rooms:index` (set): all active room ids
- `sfu:rooms:by_owner:<sub>` (set): room ids owned by a user

---

## 9) API Contract (RoMM side, planning)

We will likely add a RoMM endpoint that mints an SFU token and writes `sfu:auth:jti:<jti>`.

Candidate endpoint:

- `POST /api/sfu/token`

Auth:

- Must require an authenticated RoMM user (session cookie or OAuth bearer).

Request payload (optional):

- requested scopes
- optional room binding

Response:

- `token`: JWT
- `expires_in`: seconds
- optional: `netplay_username` (for convenience; SFU still validates from Redis)

CSRF:

- If called via cookie-auth from browser, ensure CSRF is handled correctly.

---

## 10) Federation: Trusted Sites

### 10.1 Goal

Allow multiple RoMM instances to share SFU capacity and/or lobbies based on explicit trust.

### 10.2 Trust anchor

Trusted site public keys are stored on disk:

- `/romm/config/trusted_keys/<fqdn>.pub`

The SFU uses the filename (FQDN) as the identity and verifies signed assertions using that public key.

### 10.3 Federation assertion token

Use a signed assertion (JWS) issued by a trusted site.

Claims:

- `iss`: `<peer_fqdn>`
- `aud`: `<this_site_fqdn>`
- `iat`, `exp` (very short, e.g. 30–60s)
- `nonce` (unique)
- `scope`: e.g. `federation:sfu_lobby`, `federation:sfu_worker`
- optional routing hints / requested resources

Replay protection:

- SFU stores used nonces briefly in Redis:
  - `sfu:federation:nonce:<iss>:<nonce>` with `SETEX`.

Transport:

- Always use TLS.
- Optional future: mTLS or certificate pinning.

---

## 11) Operational Notes

- Prefer a separate Redis logical DB or separate Redis instance for SFU if operationally convenient.
- Ensure SFU tokens are never logged in plaintext.
- Prefer passing tokens via `Authorization` header over query string.

---

## 12) Open Questions (to finalize)

1. Token TTL: 60s vs 180s vs longer? (trade-off: UX reconnect vs replay window)
2. One-time tokens vs reusable within TTL?
3. Netplay username storage choice (ui_settings vs new DB column).
4. Room id format and whether it should be globally unique across federation.
5. Federation key format: RSA vs Ed25519; JWK vs PEM.
6. Whether SFU needs role/scopes beyond `sfu:connect`.
