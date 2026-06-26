# RomM Permission System Redesign — Group-Based Granular Permissions

## Context

RomM's authorization today is **role → fixed scopes, baked into the JWT**:

- Three roles (`viewer` / `editor` / `admin`) in `backend/models/user.py`, each mapped to a hardcoded scope set via the `User.oauth_scopes` property (lines 110-121).
- 20 coarse scopes (`roms.read`, `platforms.write`, …) in `backend/handler/auth/constants.py`, composed hierarchically (`READ ⊂ WRITE ⊂ EDIT ⊂ FULL`).
- Enforcement is stateless: `@protected_route(method, path, [Scope.X])` (`backend/decorators/auth.py`) wraps each endpoint in Starlette's `requires(scopes)`, checking the scope set that `hybrid_auth.py` derives from the user's role and intersects with the token's claims.
- **No per-entity permissions and no per-user visibility.** All users see all platforms/ROMs (minus a personal `RomUser.hidden` toggle). Sharing is only binary `is_public` flags.

The frontend v2 layer is already built for the future: `useCan(action, scope?)` reads a `permissions` Pinia store whose `Grant`/`PermissionScope` types already model `{kind:'platform'|'rom'|…, id}`. Today it is hydrated from a **temporary hardcoded** `role-map.ts`. CLAUDE.md already lists the backend debt this redesign pays off: `/permissions/me` (#6), `ActionKey` OpenAPI enum (#5), `permissions:changed` socket event (#7).

**Goal (user-decided):**

1. Only **two user kinds**: `admin` (bypasses everything) and `user` (granular).
2. Granular **read / write / delete per entity type**, assigned via **permission groups** (named templates) **plus per-user overrides**.
3. **Opt-out visibility** (denylist): a user with read sees everything except platforms/games an admin explicitly **hides** from that user/group. Hiding a platform cascades to its ROMs and firmware.
4. New users get a **configurable default template** (a server-wide default group).
5. **Phased rollout**, backend foundation first.

**The architectural shift:** per-entity grants can't live in a stateless JWT, so authorization becomes **DB-backed, resolved per request**. The spine that keeps this safe: `User.oauth_scopes` is a single chokepoint feeding the _entire_ existing enforcement chain (Starlette `requires`, token intersection, `/token` gate, kiosk, ~30 v1 `scopes.includes()` checks). We keep that coarse layer working by **deriving `oauth_scopes` from the new model** (a projection), and add a new **fine layer** for per-entity/delete/visibility decisions on top.

---

## Target model — concepts

- **`admin` vs `user`**: a 2-value discriminator. Admins short-circuit all checks. Reuse the existing `role` column (repurposed) to avoid a wide refactor of `get_admin_users()` and the last-admin lockout.
- **Permission group**: a named template carrying a read/write/delete matrix over entity types. One **default** group (`is_default`) applies to new users. A user belongs to **one** group (single FK — simplest; a join table can come later if multi-group is ever needed).
- **Per-user override**: tri-state add/revoke on top of the group's matrix.
- **Hidden entity (denylist)**: `(entity_type, entity_id, principal=user|group)` rows. Cascade (platform → its ROMs/firmware) is computed **at query time** (anti-join), never materialized.
- **Ownership is orthogonal**: users always fully control their **own** collections/saves/states/screenshots/notes/devices/tokens via an ownership check, never via the group matrix. The existing `user_id` FKs already model ownership.
- **`is_public` sharing flags stay** as a separate axis. Precedence: **hidden (deny) > is_public (allow) > group read**.

---

## Data model (new tables)

New module `backend/models/permission.py`. Use `Enum(..., native_enum=False)` (VARCHAR + check) for portability across SQLite/MariaDB/Postgres (matches the codebase's stance).

```python
class PermEntity(StrEnum):   # entity-type vocabulary
    PLATFORMS, ROMS, COLLECTIONS, FIRMWARE, ASSETS, DEVICES, USERS, TASKS, LOGS

class PermAction(StrEnum):
    READ, WRITE, DELETE
```

- **`permission_groups`** — `id`, `name` (unique), `description`, `is_default` (bool, app-level "only one true" invariant), `is_system` (marks the auto-created legacy groups so the UI warns before edit/delete), timestamps.
- **`permission_group_grants`** — `(group_id FK CASCADE, entity, action, own_only bool)`, unique `(group_id, entity, action)`. Absence = not granted. `own_only=True` expresses "manage OWN collections/saves" presets.
- **`user_permission_overrides`** — `(user_id FK CASCADE, entity, action, granted bool, own_only bool)`, unique `(user_id, entity, action)`. `granted=True` adds, `granted=False` revokes; absence = defer to group.
- **`hidden_entities`** — `(entity, entity_id, user_id NULL, group_id NULL)` with `CHECK((user_id IS NULL) <> (group_id IS NULL))`, indexes on `(user_id, entity)` and `(group_id, entity)`. Practically only `platforms`/`roms` are hidden; firmware is excluded via the platform cascade.
- **`users.default_group_id`** — nullable FK `ON DELETE SET NULL`. A user with NULL group falls back to the server default group in the resolver.

---

## Permission resolver

New service `backend/handler/auth/permissions.py` (pure, FastAPI-free, unit-testable).

```python
@dataclass(frozen=True)
class ResolvedPermissions:
    is_admin: bool
    user_id: int
    grants: frozenset[ResolvedGrant]          # (entity, action, own_only)
    hidden_platform_ids: frozenset[int]
    hidden_rom_ids: frozenset[int]
    def allows(entity, action, *, owned=None) -> bool
    def can_see_rom(rom) -> bool               # platform_id not hidden AND id not hidden
    def can_see_platform(platform) -> bool
```

**`resolve_permissions(user, session)` precedence — admin > per-user override > group grant > default:**

1. `admin` → `is_admin=True`, bypass.
2. Start from `user.group or get_default_group()`; load its grants into a `{(entity,action): grant}` map.
3. Apply overrides: `granted=True` adds/replaces, `granted=False` pops the key.
4. Load `hidden_platform_ids` / `hidden_rom_ids` = union of user-principal and group-principal rows.

**Cascade** is applied where queries live, as an anti-join (`Rom.platform_id NOT IN hidden_platform_ids`), not by enumerating ROM ids in Python.

**Caching**: resolve once per request, cache on `request.state.permissions`. (Optional cross-request Redis cache keyed `perms:{user_id}`, invalidated on `permissions:changed` — phase-2 optimization; row counts are tiny.)

---

## Enforcement — two layers

**Coarse layer (unchanged transport gate):** `@protected_route(..., [Scope.ROMS_WRITE])` stays on every endpoint. It is now fed by a **projection** of the new model (below), so tokens, kiosk, OAuth `/token`, and v1's `scopes.includes()` all keep working untouched.

**Projection** — rewrite `User.oauth_scopes` to derive coarse scopes from resolved grants:

- `admin` → `FULL_SCOPES`.
- `user` → union of resolved grants mapped to legacy scopes (write-roms-anywhere → `ROMS_WRITE` (+`ROMS_READ`), collections-write → `COLLECTIONS_WRITE`, …). `ME_READ`/`ME_WRITE` always present (self-service).
- Because this needs a session, add `compute_oauth_scopes(user, session)` used by `hybrid_auth.py`; keep a no-session property fallback for compatibility.
- The migration backfill and this projection should **share one pure mapping module** so that on day one `role → grants → projected scopes` is the identity (provable no drift).

**Fine layer (new, additive):** `backend/handler/auth/dependencies.py`:

- `get_permissions(request) -> ResolvedPermissions` (lazy, cached on `request.state`).
- `require_permission(entity, action)` dependency factory for library-level gating.
- `assert_can(perms, entity, action, *, obj=None, owner_id=None)` / `can_access(...)` for per-resource + ownership checks inside handlers. Ownership rule: admin → ok; `owner_id == perms.user_id` → ok (even with no grant); else require a non-`own_only` grant.

**Guard pattern** (e.g. ROM delete): keep the coarse `[Scope.ROMS_WRITE]`, then inside: `assert_can(perms, ROMS, DELETE)`; hidden rom/platform → raise **404** (not 403) to avoid leaking existence.

---

## Query-time visibility filtering

Single helper applied at the end of query construction (and to count queries so totals match):

```python
def _apply_visibility(query, perms):
    if perms.is_admin: return query
    if perms.hidden_platform_ids: query = query.filter(Rom.platform_id.notin_(...))
    if perms.hidden_rom_ids:      query = query.filter(Rom.id.notin_(...))
    return query
```

- ROMs: `backend/handler/database/roms_handler.py` — wire into `get_roms_query`/`filter_roms`/`get_roms_scalar`. Coexists with the existing personal `RomUser.hidden` filter (orthogonal axes).
- Platforms: `platforms_handler.py` — `Platform.id.notin_(hidden_platform_ids)`.
- Firmware: `firmware_handler.py` — `Firmware.platform_id.notin_(hidden_platform_ids)`.
- Single-resource fetches (`get_rom`, `get_platform`, asset downloads) → **404-mask** hidden entities.
- Performance: hidden sets are tiny → literal `NOT IN (small list)` on indexed `platform_id` is cheap. Fall back to an `EXISTS` subquery only if `len(hidden) > 500`.

---

## `/permissions/me`

New `backend/endpoints/permissions.py`, gated `[Scope.ME_READ]`. Maps resolved grants onto the frontend's `useCan` vocabulary (one backend `(entity, action)` fans to several UI `ActionKey`s, e.g. `ROMS+READ → {rom.view, rom.play, rom.download, rom.favorite}`):

```jsonc
{
  "is_admin": false,
  "grants": [ { "action": "rom.view", "scope": { "kind": "global" } }, ... ],
  "hidden": { "platforms": [5, 12], "roms": [8841] }
}
```

All scopes are `{kind:'global'}` in the foundation (the model is library-wide read/write/delete; per-platform `PermissionScope` is reserved for future). `is_admin:true` makes the frontend short-circuit `useCan` to true.

---

## Migration & backfill — **parity is mandatory (nobody gains/loses access on upgrade)**

Single Alembic migration `backend/alembic/versions/0088_permission_system.py` (revises `0087`):

1. Create the four tables + `users.default_group_id`.
2. Seed two **system** groups whose matrices are **derived from the existing `*_SCOPES` constants** in `constants.py` (not hand-typed), guaranteeing equality:
   - **"Viewer (legacy)"** (`is_default=True`) == `WRITE_SCOPES`: read roms/platforms/firmware/assets/collections; write+**delete** own collections/assets/devices/roms-user data (`own_only=True`).
   - **"Editor (legacy)"** == `EDIT_SCOPES`: Viewer + read/write/**delete** roms, platforms, firmware (library-wide).
3. **Delete parity (highest-risk point, verified):** there is **no delete scope today** — delete endpoints gate on `*_WRITE`. So today's editors _can_ delete roms/platforms/firmware and viewers _can_ delete their own collections/assets. The legacy groups must therefore set **`delete=True` wherever the old `*_WRITE` scope allowed deletion**, or upgraded users lose the ability to delete. (Re-audit each delete endpoint's scope when authoring the matrix to confirm coverage.)
4. Backfill `role`: `ADMIN→admin`, `EDITOR`/`VIEWER→user`. **Keep the column with 3 physical values for now** (v1 display + OIDC still read it); narrow the enum to `admin`/`user` in a **later** migration after the admin UI ships (two-step narrowing avoids a destructive enum-alter on a column other code reads).
5. Assign `default_group_id`: old VIEWER → Viewer group, old EDITOR → Editor group, ADMIN → ignored (bypasses).
6. No overrides/hides created → zero access change on upgrade.

`downgrade()`: drop new tables + column; `role` untouched → clean rollback.

---

## Edge cases & decisions (the "loose ends")

- **First-admin bootstrap**: unchanged; setup forces `admin`. Migration seeds the default group before any non-admin exists.
- **Last-admin lockout**: extend the existing `get_admin_users()` guard (`endpoints/user.py:451`) to also block **demotion** `admin→user` (and self-demotion via the new group UI) when only one admin remains.
- **Kiosk mode**: synthetic `id=-1` user, no DB rows. Resolve specially to a fixed read-only grant set; never route through DB permission loading. Coarse projection returns `READ_SCOPES`.
- **OIDC** (`base_handler.py:418-452`): admin claim → `admin`; editor/viewer claims → `user` + the matching legacy default group via a config map (keep the `OIDC_ROLE_*` env var names — renaming is a breaking ops change). Reconcile **legacy group membership only**; never clobber admin-set custom groups/overrides.
- **Invites** (`base_handler.py:222-254`): new invites carry (kind, default-group); in-flight invites with `"EDITOR"`/`"VIEWER"` strings still map to the legacy groups (don't break outstanding invite emails).
- **Self-service invariant**: a `user` always reads/writes own profile (`ME_*`) and own data regardless of group — bake unconditionally into both projection and fine layer. _Failure mode if missed: viewers lose the ability to save game progress on upgrade._
- **`is_public` interplay**: hidden (deny) > is_public (allow) > group read. Test the cross-product (hidden platform + public collection containing its ROMs).
- **Client tokens**: keep scope-based; intersect with the fresh projection. No delete scope exists, so a `ROMS_WRITE` token passes the coarse gate then hits a clear fine-layer **403** on delete if the user lacks delete — ensure 403, not 500. Document in release notes.
- **Group deleted**: `SET NULL` → user falls back to default group; block deleting the _default_ group itself (reassign first).
- **v1 ↔ v2 parity**: both derive from the same backend model and agree at the coarse level. v1 (frozen) can't express per-entity hiding or per-entity delete, so a v1 user may _see_ a delete button the backend rejects — acceptable (backend is authority); fine-grained UX hints live only in v2.
- **`lazy="raise"` on `User.group`**: eager-load group rows in the resolver deliberately or you'll get raise-load errors on hot paths.

---

## Frontend delta (v2 only — no v1 files touched)

- **`stores/permissions.ts`**: keep `setGrants`; **delete** `hydrateFromRole` + `hydratedFromRole` + the `actionsForRole` import (dead temp code, allowed by §VIII.9). Add `isAdmin` + `hidden` to state.
- **`useCan/index.ts`**: rewrite `installPermissionsHydration` to fetch `/permissions/me` → `setGrants` on user change, `reset()` on logout, and subscribe `useSocketEvent("permissions:changed", refetch)` (the composable already exists). `useCan` itself unchanged; extend to honor `isAdmin` short-circuit.
- **`useCan/actions.ts`**: replace the hand-authored `ACTIONS` union with the generated `ActionKey` (debt #5); keep `PermissionScope`/`Grant`.
- **`useCan/role-map.ts`**: **DELETE** (in the `/permissions/me` PR).
- **ADD** `services/api/permissions.ts` (`fetchMe()`), canonical shared service.
- **REGEN** `__generated__` (`ActionKey`, `PermissionsMe`, later narrowed `Role`) via `npm run generate`.

---

## PR sequence (phased; app never breaks because PRs 1-5 preserve `oauth_scopes` exactly)

1. **Models + migration + backfill** (backend). No behavior change yet (`oauth_scopes` still reads the role switch). _Gate_: migration up/down on seeded DB; assert `oauth_scopes_old == projected_new` for every user; backend tests green.
2. **Resolver + projection.** Add `resolve_permissions`, `compute_oauth_scopes`; repoint `User.oauth_scopes` to the projection. No endpoint changes. _Gate_: parametrized projection==legacy test for admin/editor/viewer/kiosk; token-intersection tests green.
3. **OIDC + invite mapping** to (kind, group). _Gate_: OIDC unit tests per claim; reconciliation never clobbers overrides.
4. **Fine gates: delete + visibility filtering.** `assert_can` in delete endpoints; `_apply_visibility` in list/read queries; 404-masking. _Gate_: integration — write-not-delete user gets 403 on delete but passes coarse gate; hidden platform absent for that user, present for others; admin unaffected.
5. **`/permissions/me` + `permissions:changed` socket event + OpenAPI `ActionKey` enum** (debt #5/#6/#7). _Gate_: endpoint grants' `useCan` evaluation matches `actionsForRole` for legacy users (parity); `npm run generate` clean.
6. **Frontend: consume `/permissions/me`, delete role-map** (v2 additive). _Gate_: CLAUDE.md §VII sweep (typecheck, lint `./src/v2`, Vitest+stories, browser `uiVersion=v2` golden + no-permission edge, both themes, four modalities); v2 UX parity for legacy editor/viewer.
7. **Admin UI** for groups / overrides / hiding (v2 feature composites). _Gate_: §VII + manual CRUD with live `permissions:changed` propagation.
8. **Enum narrowing** `role → admin|user` + `UserSchema`/`get_admin_users` cleanup + regen. Only after PR 7. _Gate_: migration up/down; last-admin lockout correct.

---

## Critical files

**Create:** `backend/models/permission.py`, `backend/handler/auth/permissions.py`, `backend/handler/auth/dependencies.py`, `backend/handler/database/permissions_handler.py`, `backend/endpoints/permissions.py`, `backend/endpoints/responses/permission.py`, `backend/alembic/versions/0088_permission_system.py`, `frontend/src/services/api/permissions.ts`.

**Modify:** `backend/models/user.py` (repurpose `role`, add `default_group_id`+relationship, rewrite `oauth_scopes`/add `compute_oauth_scopes`, kiosk), `backend/handler/auth/{constants.py (shared mapping module), hybrid_auth.py, base_handler.py (OIDC+invites)}`, `backend/handler/database/{roms_handler.py, platforms_handler.py, firmware_handler.py, users_handler.py}`, delete/edit endpoints (`platform.py`, `rom.py`, `firmware.py`, `collection.py`, asset endpoints), `frontend/src/stores/permissions.ts`, `frontend/src/v2/composables/useCan/{index.ts, actions.ts}`.

**Delete:** `frontend/src/v2/composables/useCan/role-map.ts` (PR 6).

---

## Verification (end-to-end)

- **Backend**: `pytest` on resolver (precedence, ownership, own_only), projection-parity, migration up/down + backfill assertions, visibility filtering (list + count + 404-mask), last-admin guard, OIDC/invite mapping, kiosk read-only.
- **The parity test is the linchpin**: for a DB seeded with admin/editor/viewer users, assert each user's projected `oauth_scopes` equals their pre-migration scopes exactly — this proves the upgrade changes nobody's access.
- **Frontend** (CLAUDE.md §VII): `npm run typecheck`, `npm run lint`, `npm run test`, `npm run generate` after backend API changes. Browser-test `uiVersion=v2`: a `user` with restricted group sees gated controls hidden (`v-if`), a hidden platform absent from their gallery; admin sees everything; live update when an admin changes their permissions (socket). Both themes, four modalities.
- **Manual upgrade test**: run the migration against a populated dev DB; confirm existing editors/viewers retain identical capabilities (including delete) and visibility.
