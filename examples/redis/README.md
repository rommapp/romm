# Redis/Valkey ACL example (RomM + EmulatorJS-SFU)

This folder contains an example ACL file that defines two users:

- `romm`: admin access (used by the RomM backend and workers)
- `sfu`: least-privilege access restricted to the `sfu:*` keyspace (used by the EmulatorJS-SFU server)

## Recommended: env-driven ACL generation (no host-mounted users.acl)

Host-mounting `users.acl` can be fragile due to file ownership/permission mismatches.
The main compose example (`examples/docker-compose.example.yml`) uses a small init
script that generates the ACL inside the Valkey data volume on first start.

What you do:

- Set `ROMM_AUTH_SECRET_KEY` and `VALKEY_SFU_PASSWORD` in your `.env`
- Bring the stack up

The script writes `/data/users.acl` inside the Valkey container (persisted in the volume).

## Internal Valkey (single RomM container)

If you are using RomM's built-in Valkey (i.e. you do NOT set `REDIS_HOST`), RomM can now
generate/verify an ACL file inside `/redis-data` at startup.

To allow the SFU to connect from another container:

- Set `ROMM_INTERNAL_VALKEY_EXPOSE=true` (binds Valkey to `0.0.0.0` and disables protected-mode)
- Set `ROMM_AUTH_SECRET_KEY` and `VALKEY_SFU_PASSWORD`
- Set `REDIS_USERNAME=romm` (optional; RomM will default it when ACL is enabled)

If you prefer separate secrets, set `VALKEY_ROMM_PASSWORD` (or `REDIS_PASSWORD`) explicitly.

You do NOT need to publish port `6379` to the host if the SFU is in the same Docker network; it can
connect directly to the RomM service name on port 6379.

## How to use

### Option A: generate inside the container (recommended)

1. Set passwords in your `.env`:
   - `ROMM_AUTH_SECRET_KEY=...` (also used as the `romm` ACL password in the example)
   - `VALKEY_SFU_PASSWORD=...`
2. Use the provided compose example which will generate `/data/users.acl` automatically.

### Option B: provide a static users.acl (manual)

1. Copy [users.acl.example](users.acl.example) to `users.acl`.
2. Replace the placeholder passwords:
   - `CHANGEME_ROMM_REDIS_PASSWORD`
   - `CHANGEME_SFU_REDIS_PASSWORD`
3. Mount this folder into your Valkey/Redis container (read-only is fine).
4. Start Valkey/Redis with `--aclfile /etc/valkey/users.acl` (path depends on your image).

## Environment variables

RomM container:

- `REDIS_HOST=<valkey service name>`
- `REDIS_PORT=6379`
- `REDIS_USERNAME=romm`
- `REDIS_PASSWORD=<CHANGEME_ROMM_REDIS_PASSWORD>` (defaults to `ROMM_AUTH_SECRET_KEY` in the example)

Note: RomM background workers (RQ) use Redis Pub/Sub channels (e.g. `rq:pubsub:*`).
In Redis ACL, channel permissions are controlled by `&` patterns, separate from key
patterns (`~`). The example `romm` user includes `&*` to allow required Pub/Sub.

SFU container:

- `ROMM_AUTH_SECRET_KEY=<same value as RomM>` (or `SFU_AUTH_SECRET_KEY`)
- `SFU_AUTH_REDIS_URL=redis://sfu:<CHANGEME_SFU_REDIS_PASSWORD>@<valkey service name>:6379/0`

Note: do NOT set `REDIS_URL` unless you are intentionally enabling the optional
multi-node room registry. Leaving it unset keeps the SFU's Redis permissions
minimal (auth-only) and avoids needing `SCAN`/`MGET` privileges.

## Verify

- RomM user: `redis-cli -h <host> -p 6379 --user romm -a '<password>' PING`
- SFU user: `redis-cli -h <host> -p 6379 --user sfu -a '<password>' PING`

The `sfu` user should NOT be able to read outside `sfu:*`.
