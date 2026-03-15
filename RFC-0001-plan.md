# RFC 0001: Device Registration and Multi-Protocol Save Synchronization — Implementation Plan

## Context

Cross-device save synchronization is needed for RomM's expanding client ecosystem. The RFC defines three sync modes (API, File Transfer, Push-Pull) to accommodate devices with varying capabilities. The codebase already has foundational pieces: a `Device` model with `SyncMode` enum, `DeviceSaveSync` tracking, and save endpoints with conflict detection. This plan builds on those foundations.

Implementation is split into 3 phases. **Phase 1 (API Mode)** is the immediate priority as it enables smart client apps. Phases 2 and 3 are outlined but will be planned in detail when Phase 1 is complete.

---

## Phase 1: Foundation & API Sync Mode

### 1. Database Schema Changes

**Modify `backend/models/device.py`** — Add `sync_config` JSON column:

```python
sync_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Stores mode-specific configuration (SSH config for push-pull, sync folder for file transfer, save format preferences).

**Create `backend/models/sync_session.py`** — New `SyncSession` model:

- `id`: Integer PK, autoincrement
- `device_id`: String FK -> devices.id (CASCADE)
- `user_id`: Integer FK -> users.id (CASCADE)
- `status`: Enum (pending, in_progress, completed, failed, cancelled)
- `initiated_at`: TIMESTAMP
- `completed_at`: TIMESTAMP (nullable)
- `operations_planned`: Integer (default 0)
- `operations_completed`: Integer (default 0)
- `operations_failed`: Integer (default 0)
- `error_message`: String(1000), nullable
- Relationships: `device`, `user`

**Create `backend/alembic/versions/0073_sync_sessions.py`** — Migration:

- Creates `sync_sessions` table
- Adds `sync_config` JSON column to `devices`
- Adds indexes on `device_id`, `user_id`, `status`

### 2. Shared Comparison Algorithm

**Create `backend/handler/sync/__init__.py`** and **`backend/handler/sync/comparison.py`**

Extract the save comparison logic into a reusable function used by all three sync modes:

```python
def compare_save_state(
    client_hash: str | None,
    client_updated_at: datetime,
    server_hash: str | None,
    server_updated_at: datetime,
    device_last_synced_at: datetime | None,
) -> SyncComparisonResult:  # action: upload | download | conflict | no_op
```

Rules:

- Same hash → `no_op`
- Client has save, server doesn't → `upload`
- Server has save, client doesn't → `download` (or `no_op` if device previously synced and intentionally deleted)
- Both have save, different hash → compare timestamps; client newer → `upload`, server newer → `download`, ambiguous → `conflict`

### 3. Sync Session DB Handler

**Create `backend/handler/database/sync_sessions_handler.py`**

Methods: `create_session`, `get_session`, `get_active_session`, `update_session`, `complete_session`, `fail_session`, `get_sessions`

**Modify `backend/handler/database/__init__.py`** — Register `db_sync_session_handler`.

### 4. Sync Negotiation Endpoint

**Create `backend/endpoints/sync.py`** — Router at `/sync`

Core endpoint: `POST /api/sync/negotiate`

Request payload:

```python
class ClientSaveState(BaseModel):
    rom_id: int
    file_name: str
    slot: str | None = None
    emulator: str | None = None
    content_hash: str | None = None
    updated_at: datetime
    file_size_bytes: int

class SyncNegotiatePayload(BaseModel):
    device_id: str
    saves: list[ClientSaveState]
```

Response (in **`backend/endpoints/responses/sync.py`**):

```python
class SyncOperation(BaseModel):
    action: Literal["upload", "download", "conflict", "no_op"]
    rom_id: int
    save_id: int | None = None
    file_name: str
    slot: str | None = None
    reason: str
    server_updated_at: datetime | None = None
    server_content_hash: str | None = None

class SyncNegotiateResponse(BaseModel):
    session_id: int
    operations: list[SyncOperation]
    total_upload: int
    total_download: int
    total_conflict: int
    total_no_op: int
```

Negotiation logic:

1. Validate device exists and belongs to user
2. Cancel any existing active session for this device
3. Create new `SyncSession` (pending)
4. For each client save: look up server save by `(rom_id, user_id, file_name)` or `(rom_id, user_id, slot)`, then run comparison algorithm
5. Check for server saves the client didn't mention (tracked, not untracked) → `download`
6. Return operations list

Additional endpoints:

- `POST /api/sync/{session_id}/complete` — mark session done
- `GET /api/sync/sessions` — list sessions for a device
- `GET /api/sync/sessions/{session_id}` — session detail

### 5. Modifications to Existing Code

**`backend/endpoints/device.py`** — Add `sync_mode` and `sync_config` to `DeviceCreatePayload` and `DeviceUpdatePayload`.

**`backend/endpoints/responses/device.py`** — Add `sync_config: dict | None = None` to `DeviceSchema`.

**`backend/endpoints/saves.py`** — Add optional `session_id: int | None = None` parameter to `add_save` and `download_save`. When provided, increment `operations_completed` on the session.

**`backend/main.py`** — Register sync router.

### 6. Files Summary

| Action | File                                                              |
| ------ | ----------------------------------------------------------------- |
| Create | `backend/models/sync_session.py`                                  |
| Create | `backend/alembic/versions/0073_sync_sessions.py`                  |
| Create | `backend/handler/sync/__init__.py`                                |
| Create | `backend/handler/sync/comparison.py`                              |
| Create | `backend/handler/database/sync_sessions_handler.py`               |
| Create | `backend/endpoints/sync.py`                                       |
| Create | `backend/endpoints/responses/sync.py`                             |
| Modify | `backend/models/device.py` — add `sync_config` column             |
| Modify | `backend/handler/database/__init__.py` — register handler         |
| Modify | `backend/endpoints/device.py` — sync_config/sync_mode in payloads |
| Modify | `backend/endpoints/responses/device.py` — sync_config in schema   |
| Modify | `backend/endpoints/saves.py` — optional session_id                |
| Modify | `backend/main.py` — register router                               |

---

## Phase 2: File Transfer Mode (Outline)

- Add `SYNC_BASE_PATH` config and `ENABLE_SYNC_FOLDER_WATCHER` flag
- Create sync folder watcher (`backend/watcher_sync.py`) following `backend/watcher.py` patterns
- Create periodic scan task (`backend/tasks/sync_folder_task.py`) as fallback
- Auto-create device sync folder structure on FILE_TRANSFER registration
- Folder convention: `/romm/sync/{device_id}/incoming/{platform_slug}/` and `.../outgoing/`
- Reuse comparison algorithm from Phase 1
- Extend `fs_asset_handler` with sync folder path builders

## Phase 3: Push-Pull Mode (Outline)

- Add `asyncssh` dependency
- Create SSH/SFTP handler (`backend/handler/sync/ssh_handler.py`)
- Create periodic push-pull task (`backend/tasks/sync_push_pull_task.py`)
- Add manual trigger endpoint: `POST /api/sync/{device_id}/push-pull`
- Add SSH key management endpoints
- WebSocket notifications for sync progress (`backend/endpoints/sockets/sync.py`)
- Reuse comparison algorithm from Phase 1

---

## Verification

1. **Unit tests**: Test comparison algorithm with all edge cases (same hash, client-only, server-only, newer/older, conflicts)
2. **Integration tests**: Full negotiate → upload/download → complete session flow (in `backend/tests/endpoints/test_sync.py`)
3. **Device tests**: Registration with sync_config, update sync_mode
4. **Session lifecycle**: Create, complete, fail, cancel
5. **Manual testing**: Use the existing save endpoints with session_id tracking
