import asyncio
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import aiohttp
from fastapi import Body, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, Response, WebSocket, status
from pydantic import BaseModel
from rq.command import send_stop_job_command
from starlette.authentication import requires
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, StreamingResponse
from starlette.websockets import WebSocketState

from config import DEV_MODE, INSTALL_MAX_CONCURRENCY, INSTALL_WORKER_HOST, ROMM_BASE_URL
from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses.install import (
    CustomProtonBuildForm,
    InstallCacheClearSchema,
    InstallCacheEntrySchema,
    InstallCacheSchema,
    InstallCandidateSchema,
    InstallCandidatesSchema,
    InstallDashboardEntrySchema,
    InstallDashboardSchema,
    InstallFileSchema,
    InstallFilesSchema,
    InstallSessionSchema,
    InstallStreamFileSchema,
    InstallStreamManifestSchema,
    InstallWorkerStatusSchema,
    ProtonBuildSchema,
    ProtonBuildsSchema,
    ProtonDownloadProgressSchema,
    ProtonDownloadResponseSchema,
)
from exceptions.config_exceptions import ConfigNotWritableException
from exceptions.endpoint_exceptions import (
    InstallConcurrencyLimitException,
    InstallSessionHasViewersException,
    InstallSessionNotActiveException,
    InstallSessionNotFoundException,
    InstallSessionRunningException,
    InstallWorkerUnavailableException,
    ProtonBuildNotFoundException,
    RomNotFoundInDatabaseException,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_install_session_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.installer_detection import (
    ARCHIVE_SOURCE_KINDS,
    INSTALLABLE_PLATFORM_SLUGS,
    pick_default_installer,
)
from handler.install import bandwidth, stream_presence
from handler.install.archive_prescan import is_archive_candidate, list_source_candidates
from handler.install.manifest import (
    find_manifest_entry,
    live_view_of_final_manifest,
    manifest_total_bytes,
    read_live_manifest,
    read_manifest,
)
from handler.install.proton_builds import (
    CUSTOM_ID_PREFIX,
    custom_build_id,
    get_custom_builds,
    list_proton_builds,
    remove_build,
    resolve_effective_build,
)
from handler.install.queue_status import has_install_worker
from handler.install.runner import enqueue_install
from handler.install.stream_copy import enqueue_stream_copy
from handler.redis_handler import redis_client
from logger.logger import log
from models.install_session import (
    ACTIVE_INSTALL_STATES,
    RUNNING_INSTALL_STATES,
    InstallSession,
    InstallSessionState,
)
from utils.context import ctx_aiohttp_session
from utils.install_cache import (
    cache_root_dirs,
    clear_session_cache,
    dir_size_bytes,
    purge_superseded_sessions,
    resolve_expires_at,
    session_cache_dir,
)
from utils.nginx import FileRedirectResponse, ZipContentLine, ZipResponse
from utils.router import APIRouter
from utils.ssrf import validate_url_for_http_request
from utils.validation import ValidationError
from utils.zip_cache import ensure_zipfile_writable

router = APIRouter()


class InstallStartForm(BaseModel):
    """Request body to start (or restart) an install session for a ROM."""

    # Relative path of the installer to run. Required when the ROM needs an
    # installer and none was auto-detected (needs_manual_pick was true).
    installer_path: str | None = None
    # Archive or disc image (relative to the ROM's directory) holding the
    # installer. When set, `installer_path` names the executable inside it
    # (None picks the top-ranked one after unpacking).
    source_path: str | None = None
    # Proton build id to run this installer under (see
    # handler.install.proton_builds). None (or an unknown/uninstalled id)
    # falls back to the server default.
    proton_build: str | None = None
    # Cache lifetime in seconds. ``None`` uses the configured default TTL,
    # a value <= 0 means unlimited (never auto-evict).
    ttl_seconds: int | None = None
    # Experimental auto mode: OCR the installer and press its buttons. ``None``
    # uses the configured default (off unless enabled in the settings).
    auto_mode: bool | None = None
    # Force manual mode for this install (AWAITING_INSTALLER), even when
    # candidates exist. Useful when the user wants to pick the installer
    # themselves. Does not change the global setting.
    manual_mode: bool | None = None


class InstallAutoModeForm(BaseModel):
    """Request body to switch auto mode on or off while a session runs."""

    enabled: bool


def _session_schema(rom_id: int, session: InstallSession) -> InstallSessionSchema:
    """Build the response schema, filling in `manual_install_url` for a
    session that's actually waiting on one (see the field's own docstring) -
    every endpoint that returns a session goes through this so no client
    (this includes polling `GET /{id}/install`, not just the initial POST)
    ever sees AWAITING_INSTALLER without also getting the URL to send a
    human to.
    """
    schema = InstallSessionSchema.model_validate(session)
    if schema.state == InstallSessionState.AWAITING_INSTALLER:
        schema.manual_install_url = f"{ROMM_BASE_URL}/rom/{rom_id}/install"
    return schema


_CONCURRENCY_LOCK_KEY = "install:concurrency-reservation"
_CONCURRENCY_LOCK_TTL_SECONDS = 30
_CONCURRENCY_LOCK_POLL_INTERVAL_SECONDS = 0.05


def _acquire_concurrency_lock(timeout: float = 10.0) -> bool:
    """A short-lived, coarse mutual-exclusion lock around the
    count-then-transition below, so two concurrent start requests can't both
    pass the concurrency check before either reserves its slot.

    Plain ``SET NX EX`` + ``DELETE`` rather than a Lua-script-backed lock
    (e.g. ``redis_client.lock()``), matching this codebase's other Redis
    flags: the tiny window where a slow caller's key could be deleted by a
    later one after its own TTL expired is an accepted trade-off for a
    concurrency guard that isn't a data-integrity boundary.
    """
    deadline = time.monotonic() + timeout
    while True:
        if redis_client.set(
            _CONCURRENCY_LOCK_KEY, "1", nx=True, ex=_CONCURRENCY_LOCK_TTL_SECONDS
        ):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_CONCURRENCY_LOCK_POLL_INTERVAL_SECONDS)


def _pick_reusable_session(sessions: list[InstallSession]) -> InstallSession | None:
    """The session that owns this game's install cache: the newest one whose
    cache directory exists, preferring a finished install over a partial one."""
    with_cache = [
        x
        for x in sessions
        if session_cache_dir(x.id).is_dir()
        or x.state
        in (InstallSessionState.DETECTING, InstallSessionState.AWAITING_INSTALLER)
    ]
    if not with_cache:
        return None
    with_cache.sort(
        key=lambda x: (x.state == InstallSessionState.DONE, x.created_at, x.id),
        reverse=True,
    )
    return with_cache[0]


def _resolve_session(
    rom_id: int, user_id: int, session_id: int | None
) -> InstallSession | None:
    """The session a read endpoint should serve.

    A caller that already has a session id (it started or discovered this
    exact attempt earlier) gets pinned to it, so it keeps reading that
    attempt's own cache directory even if a newer, unrelated attempt for the
    same ROM starts in the meantime - without this, every read endpoint here
    resolved "the latest session for this ROM+user" implicitly, so a second
    client (or the same one, pressing Install again after the first attempt
    already finished) would silently yank a still-streaming client onto a
    brand new, empty session and 404 it. A first-time caller with no id yet
    (the web UI's own "just opened /rom/{id}/install" case, and this is the
    default for every existing client/route) still gets the latest one.
    """
    if session_id is not None:
        session = db_install_session_handler.get_session(session_id)
        if session is None or session.rom_id != rom_id or session.user_id != user_id:
            return None
        return session
    return db_install_session_handler.get_latest_session_for_rom(rom_id, user_id)


@protected_route(
    router.get,
    "/{id}/install/candidates",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_install_candidates(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    source: str | None = None,
) -> InstallCandidatesSchema:
    """Detect installer candidates for a Windows ROM.

    With `source` (an archive or disc image from the ROM's own candidates),
    lists the executables inside it instead, read from its member listing
    without extracting anything.

    Returns a ranked list of files that could serve as the installer entry
    point. When nothing is detected the client must present a manual file
    picker. Non-Windows platforms are flagged for direct stream-copy instead.

    Purely a filesystem scan (`fs_rom_handler.get_installer_candidates`) -
    no job is enqueued here, so this doesn't need (and must not require) an
    install-sandbox worker to be connected. Manual mode (AWAITING_INSTALLER,
    see `start_install_session`) is meant to work without one; gating this
    listing behind `has_install_worker()` would defeat that for any client
    that fetches candidates before/without ever calling `POST /install`.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    is_installable = rom.platform.slug in INSTALLABLE_PLATFORM_SLUGS

    if source is not None:
        try:
            source_abs = Path(fs_rom_handler.resolve_installer_abs_path(rom, source))
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        if not is_archive_candidate(source_abs):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source is not an archive or disc image",
            )
        candidates = await run_in_threadpool(list_source_candidates, source_abs)
    else:
        candidates = fs_rom_handler.get_installer_candidates(rom)

    return InstallCandidatesSchema(
        rom_id=rom.id,
        candidates=[
            InstallCandidateSchema(
                path=c.path,
                file_name=c.file_name,
                file_size_bytes=c.file_size_bytes,
                rank=c.rank,
                kind=c.kind,
            )
            for c in candidates
        ],
        needs_manual_pick=is_installable and len(candidates) == 0,
        # A ROM outside INSTALLABLE_PLATFORM_SLUGS doesn't need an installer;
        # the client stream-copies it instead.
        stream_copy=not is_installable,
    )


@protected_route(
    router.post,
    "/{id}/install",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def start_install_session(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    data: Annotated[InstallStartForm, Body()],
) -> InstallSessionSchema:
    """Create (or return) the install session for a ROM.

    Idempotent: an already-running session (INSTALLING/STREAMING) is
    returned as-is. Otherwise this always starts a fresh attempt (new
    session, new cache) even if the ROM was already installed - there is no
    separate "Reinstall" concept. A client that only wants to resume
    streaming an already-DONE install without touching the worker should
    check `GET /{id}/install` itself first instead of calling this.

    With no installer_path/source_path, the top-ranked candidate is picked
    automatically (`pick_default_installer`, unpacking an archive/disc image
    first if needed). A ROM with no candidate at all, or `manual_mode=True`,
    sits in AWAITING_INSTALLER with `manual_install_url` set instead.
    `auto_mode` (default from Settings) has the worker OCR the installer and
    press its own buttons; it can be flipped later via
    `PATCH /{id}/install/auto-mode`.

    Otherwise (Windows with a resolved path, or any non-Windows ROM): the
    sandbox runner (or stream-copy) is enqueued immediately.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    # One install cache per game: pressing Install again installs into the
    # same cache (and Wine prefix), so a patch finds the game it patches.
    rom_sessions = db_install_session_handler.get_sessions_for_rom(rom.id)
    running = next((x for x in rom_sessions if x.state in RUNNING_INSTALL_STATES), None)
    if running:
        return _session_schema(rom.id, running)
    # Only this user's own sessions are candidates for reuse - a session (and
    # its cache) started by someone else is never picked up and reassigned,
    # even if it's the only one around for this ROM.
    own_sessions = [x for x in rom_sessions if x.user_id == request.user.id]
    existing = _pick_reusable_session(own_sessions)

    is_installable = rom.platform.slug in INSTALLABLE_PLATFORM_SLUGS

    installer_path = data.installer_path
    source_path = data.source_path
    manual_mode = data.manual_mode if data.manual_mode is not None else False
    if is_installable and installer_path is None and source_path is None:
        candidates = fs_rom_handler.get_installer_candidates(rom)
        default = pick_default_installer(candidates)
        if default is not None:
            if default.kind in ARCHIVE_SOURCE_KINDS:
                source_path = default.path
            else:
                installer_path = default.path
    needs_manual_pick = is_installable and (
        manual_mode or (not installer_path and not source_path)
    )

    # Resolved now (not left NULL for the worker to decide implicitly) so the
    # client can poll /install/proton/{id}/progress and show "Downloading
    # Proton X…" instead of a silent stall while the worker auto-downloads it
    # on first use - see resolve_effective_build's own docstring.
    proton_build = (
        resolve_effective_build(data.proton_build) if is_installable else None
    )

    initial_state = (
        InstallSessionState.AWAITING_INSTALLER
        if needs_manual_pick
        else InstallSessionState.DETECTING
    )
    previous_state = existing.state if existing else None
    auto_mode = (
        data.auto_mode
        if data.auto_mode is not None
        else cm.get_config().INSTALL_AUTO_MODE
    )
    if existing:
        session = db_install_session_handler.update_session(
            existing.id,
            {
                "user_id": request.user.id,
                "installer_path": installer_path,
                "source_path": source_path,
                "phase": None,
                "phase_detail": None,
                "proton_build": proton_build,
                "auto_mode": auto_mode,
                "manual_mode": manual_mode,
                "auto_status": None,
                "auto_detail": None,
                "state": initial_state,
                "error": None,
                "vnc_url": None,
                "vnc_web_port": None,
                "expires_at": resolve_expires_at(data.ttl_seconds),
            },
        )
    else:
        # Every session starts non-running regardless of platform: the
        # concurrency check below must count sessions already running, not
        # this brand-new one. Flipping straight to STREAMING here for a ROM
        # outside INSTALLABLE_PLATFORM_SLUGS would count this session
        # against itself and reject every stream-copy install outright once
        # INSTALL_MAX_CONCURRENCY sessions (default 1) exist anywhere,
        # including itself.
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=request.user.id,
                state=initial_state,
                installer_path=installer_path,
                source_path=source_path,
                proton_build=proton_build,
                auto_mode=auto_mode,
                manual_mode=manual_mode,
                expires_at=resolve_expires_at(data.ttl_seconds),
            )
        )

    def _abandon() -> None:
        # A reused session owns the game's cache, so it goes back to what it
        # was instead of being deleted.
        if existing and previous_state is not None:
            db_install_session_handler.update_session(
                session.id, {"state": previous_state}
            )
        else:
            db_install_session_handler.delete_session(session.id)

    # Duplicates left by older versions (one cache per attempt), scoped to
    # this user - never touches another user's sessions or caches.
    purge_superseded_sessions(rom.id, session.id, request.user.id)

    # A ROM in INSTALLABLE_PLATFORM_SLUGS with a resolved installer can start
    # running immediately; one still awaiting a manual pick stays in
    # AWAITING_INSTALLER. A ROM outside that set has nothing to run, so it
    # goes straight to copying.
    if needs_manual_pick:
        return _session_schema(rom.id, session)

    # Checking count_running_sessions() and then transitioning this session
    # into a running state are two separate steps; without a lock around
    # both, two concurrent requests can each see room under
    # INSTALL_MAX_CONCURRENCY and both proceed, together exceeding it (and,
    # if they share a reused cache, race to overwrite each other's job_id
    # while both workers write into the same directory). The lock serializes
    # the whole reserve-and-enqueue critical section across requests.
    if not _acquire_concurrency_lock():
        _abandon()
        raise InstallConcurrencyLimitException(INSTALL_MAX_CONCURRENCY)
    try:
        if (
            db_install_session_handler.count_running_sessions()
            >= INSTALL_MAX_CONCURRENCY
        ):
            _abandon()
            raise InstallConcurrencyLimitException(INSTALL_MAX_CONCURRENCY)

        # Without this, enqueueing onto an unattended queue leaves the session
        # stuck "installing"/"streaming" forever: nothing ever touches its job to
        # trigger a failure, so the client polls indefinitely for a state change
        # that will never come.
        if not has_install_worker():
            _abandon()
            raise InstallWorkerUnavailableException()

        if is_installable:
            job_id = enqueue_install(session.id)
            session = db_install_session_handler.update_session(
                session.id,
                {"state": InstallSessionState.INSTALLING, "job_id": job_id},
            )
        else:
            job_id = enqueue_stream_copy(session.id)
            session = db_install_session_handler.update_session(
                session.id,
                {"state": InstallSessionState.STREAMING, "job_id": job_id},
            )
    finally:
        redis_client.delete(_CONCURRENCY_LOCK_KEY)

    return _session_schema(rom.id, session)


@protected_route(
    router.get,
    "/{id}/install",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_install_session(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    session_id: int | None = None,
) -> InstallSessionSchema:
    """Return an install session for this user+ROM: a specific one if
    `session_id` is given (see `_resolve_session`), otherwise the latest.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)
    return _session_schema(rom.id, session)


@protected_route(
    router.patch,
    "/{id}/install/auto-mode",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def set_install_auto_mode(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    data: Annotated[InstallAutoModeForm, Body()],
    session_id: int | None = None,
) -> InstallSessionSchema:
    """Switch the experimental auto mode on or off for a session.

    The worker re-reads the flag every few seconds, so this also works while
    the installer is running. Turning it off clears the status shown to the
    user; turning it on resets a previous "needs manual" warning.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)
    session = db_install_session_handler.update_session(
        session.id,
        {"auto_mode": data.enabled, "auto_status": None, "auto_detail": None},
    )
    return _session_schema(rom.id, session)


@protected_route(
    router.delete,
    "/{id}/install",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def clear_install_session(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> None:
    """Clear the install cache and remove the latest session for this user+ROM.

    Backs the "Clear Install Cache" action. Deletes the on-disk cache directory
    and the session row so a fresh install can start clean.

    Refuses (409) while another client is actively streaming from this exact
    session (see handler.install.stream_presence - the same heartbeat the
    "N viewers" counter already uses), not just while the install itself is
    still running: a DONE session's cache is exactly what a client keeps
    pulling from after the install finished, and deleting the files out from
    under an in-flight download is destructive regardless of the session's
    own state.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = db_install_session_handler.get_latest_session_for_rom(
        rom.id, request.user.id
    )
    if not session:
        raise InstallSessionNotFoundException(id)
    if session.state in RUNNING_INSTALL_STATES:
        raise InstallSessionRunningException(id)
    viewer_count = await stream_presence.count_viewers(session.id)
    if viewer_count > 0:
        raise InstallSessionHasViewersException(id, viewer_count)

    clear_session_cache(session.id)
    db_install_session_handler.delete_session(session.id)


@protected_route(
    router.post,
    "/{id}/install/cancel",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def cancel_install_session(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    clear_cache: bool = True,
) -> InstallSessionSchema:
    """Abort a running install, optionally clearing whatever partial cache
    it left.

    Best-effort: asks RQ to stop the job if a worker is still actually
    working on it, then unconditionally marks the session FAILED - RQ kills
    the job's whole process group outright (SIGKILL), so there's no graceful
    in-job cleanup to wait for; this call (or a later, separate
    `DELETE /{id}/install`) is the cleanup.

    `clear_cache` (default True, matching this endpoint's original
    behavior) controls whether that cleanup happens now: a client that asks
    the user "keep the partial download or clear it?" before calling this
    (see the web UI's own two-step abort confirmation) passes False when
    the user chose to keep it - the session and its on-disk files are left
    exactly as they were, just no longer running, so pressing Install again
    later gets the normal "already has a cache" choice instead of silently
    losing whatever had already downloaded.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = db_install_session_handler.get_latest_session_for_rom(
        rom.id, request.user.id
    )
    if not session:
        raise InstallSessionNotFoundException(id)
    if session.state not in ACTIVE_INSTALL_STATES:
        raise InstallSessionNotActiveException(id)

    if session.job_id:
        try:
            send_stop_job_command(redis_client, session.job_id)
        except Exception as e:  # noqa: BLE001 - the job may already be gone
            log.debug(f"Couldn't send stop command for job {session.job_id}: {e}")

    if clear_cache:
        clear_session_cache(session.id)
    session = db_install_session_handler.update_session(
        session.id,
        {
            "state": InstallSessionState.FAILED,
            "error": "Cancelled by user",
            "vnc_url": None,
            "vnc_web_port": None,
        },
    )
    return InstallSessionSchema.model_validate(session)


@protected_route(
    router.get,
    "/install/worker-status",
    [Scope.ROMS_INSTALL],
)
async def install_worker_status(request: Request) -> InstallWorkerStatusSchema:
    """Whether an install-sandbox worker is currently connected.

    Drives whether the client offers "Install" at all; checked live rather
    than gated behind a static setting (see has_install_worker).
    """
    return InstallWorkerStatusSchema(available=has_install_worker())


@protected_route(
    router.get,
    "/install/proton-builds",
    [Scope.PLATFORMS_WRITE],
)
async def get_proton_builds(request: Request) -> ProtonBuildsSchema:
    """Proton builds this server knows about, installed or not.

    Installed builds are discovered at runtime by the ProtonBuildManager
    scanning PROTON_INSTALL_ROOT. Not-yet-installed builds come from upstream
    release APIs and can be downloaded via POST /install/proton/{id}/download.
    Only an installed build can be used for an install session - the frontend
    marks non-installed builds as disabled/selectable-for-download so the user
    can set them as the default (they auto-download on first use on the worker).
    """
    return ProtonBuildsSchema(
        builds=[
            ProtonBuildSchema(
                id=b.id,
                label=b.label,
                installed=b.installed,
                version=b.version,
                path=b.path,
                source=b.source,
                size_bytes=b.size_bytes,
                custom=b.custom,
            )
            for b in list_proton_builds()
        ]
    )


@protected_route(
    router.post,
    "/install/proton-builds/custom",
    [Scope.PLATFORMS_WRITE],
)
async def add_custom_proton_build(
    request: Request, data: Annotated[CustomProtonBuildForm, Body()]
) -> ProtonBuildSchema:
    """Add a user-supplied Proton build (name + tarball URL).

    It is listed with the other builds and downloaded on first use, through
    the same worker download path as the upstream ones.
    """
    name = data.name.strip()
    url = data.url.strip()
    if not name or len(name) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must be 1-64 characters",
        )
    build_id = custom_build_id(name)
    if build_id == CUSTOM_ID_PREFIX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must contain letters or digits",
        )
    try:
        validate_url_for_http_request(url, "Download URL")
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    existing = get_custom_builds()
    if any(custom_build_id(b["name"]) == build_id for b in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A custom build named '{name}' already exists",
        )
    try:
        cm.update_install_settings(
            download_speed_limit_bytes_per_sec=cm.config.INSTALL_DOWNLOAD_SPEED_LIMIT_BYTES_PER_SEC,
            custom_proton_builds=[*existing, {"name": name, "url": url}],
        )
    except ConfigNotWritableException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
    return ProtonBuildSchema(
        id=build_id, label=name, installed=False, source="upstream", custom=True
    )


@protected_route(
    router.delete,
    "/install/proton-builds/custom/{build_id}",
    [Scope.PLATFORMS_WRITE],
)
async def delete_custom_proton_build(request: Request, build_id: str) -> None:
    """Remove a user-added build from the list (and its files, if extracted
    where this process can see them)."""
    existing = get_custom_builds()
    remaining = [b for b in existing if custom_build_id(b["name"]) != build_id]
    if len(remaining) == len(existing):
        raise ProtonBuildNotFoundException(build_id)
    try:
        cm.update_install_settings(
            download_speed_limit_bytes_per_sec=cm.config.INSTALL_DOWNLOAD_SPEED_LIMIT_BYTES_PER_SEC,
            custom_proton_builds=remaining,
        )
    except ConfigNotWritableException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
    remove_build(build_id)


@protected_route(
    router.post,
    "/install/proton/{build_id}/download",
    [Scope.ROMS_INSTALL],
)
async def download_proton_build(
    request: Request,
    build_id: str,
) -> ProtonDownloadResponseSchema:
    """Enqueue a Proton build download on the install worker.

    Returns the RQ job id immediately (202-style); the frontend polls
    GET /install/proton/{build_id}/progress for completion. Only builds that
    are listed as not-installed (source="upstream") can be downloaded.
    """
    builds = list_proton_builds()
    match = next((b for b in builds if b.id == build_id), None)
    if match is None or match.installed:
        raise ProtonBuildNotFoundException(build_id)

    from handler.install.proton_builds import enqueue_download

    job_id = enqueue_download(build_id)
    return ProtonDownloadResponseSchema(job_id=job_id)


@protected_route(
    router.get,
    "/install/proton/{build_id}/progress",
    [Scope.ROMS_INSTALL],
)
async def get_proton_download_progress(
    request: Request,
    build_id: str,
) -> ProtonDownloadProgressSchema:
    """Download progress (0.0-1.0) for a Proton build, or None if not in progress.

    Returns ``extracting: true`` (progress=0.0) while the tarball is being
    unpacked, so the client can show "Installing Proton…" instead of a stale
    100 % from the completed download phase.
    """
    from handler.install.proton_builds import get_download_progress, is_extracting

    progress = get_download_progress(build_id)
    extracting = is_extracting(build_id)
    return ProtonDownloadProgressSchema(progress=progress, extracting=extracting)


@protected_route(
    router.delete,
    "/install/proton/{build_id}",
    [Scope.PLATFORMS_WRITE],
)
async def delete_proton_build(
    request: Request,
    build_id: str,
) -> dict[str, str]:
    """Remove a runtime-downloaded Proton build from disk.

    Only builds under PROTON_INSTALL_ROOT that were downloaded at runtime
    can be removed; baked-in image builds are not affected.
    """

    remove_build(build_id)
    return {"message": f"Proton build {build_id} removed"}


@protected_route(
    router.get,
    "/install/dashboard",
    [Scope.ROMS_INSTALL],
)
async def install_dashboard(request: Request) -> InstallDashboardSchema:
    """This user's install sessions worth surfacing on the Home page.

    One entry per ROM: still-active sessions and finished ones with a cache
    still on disk. Backs the "Active Installers" widget, which only renders
    when this list is non-empty. Entries for a ROM the caller can no longer
    see (a permission changed after the session was created) are dropped.
    """
    from handler.auth.dependencies import get_permissions

    perms = get_permissions(request)
    sessions = db_install_session_handler.get_dashboard_sessions_for_user(
        request.user.id
    )
    entries = []
    for session in sessions:
        rom = db_rom_handler.get_rom(session.rom_id)
        if not rom or not perms.can_see_rom(rom.id, rom.platform_id):
            continue
        entries.append(
            InstallDashboardEntrySchema(
                session=InstallSessionSchema.model_validate(session),
                rom_id=rom.id,
                rom_name=rom.name,
                platform_slug=rom.platform_slug,
                path_cover_small=rom.path_cover_small,
            )
        )
    return InstallDashboardSchema(entries=entries)


def _build_cache_listing() -> InstallCacheSchema:
    sessions = {s.id: s for s in db_install_session_handler.get_all_sessions()}
    entries: list[InstallCacheEntrySchema] = []
    total = 0
    for directory in cache_root_dirs():
        size = dir_size_bytes(directory)
        total += size
        session = (
            sessions.get(int(directory.name)) if directory.name.isdigit() else None
        )
        if session is None:
            continue
        rom = db_rom_handler.get_rom(session.rom_id)
        entries.append(
            InstallCacheEntrySchema(
                session_id=session.id,
                rom_id=session.rom_id,
                rom_name=rom.name if rom else None,
                platform_slug=rom.platform_slug if rom else None,
                user_id=session.user_id,
                state=session.state,
                size_bytes=size,
                created_at=session.created_at,
                updated_at=session.updated_at,
                expires_at=session.expires_at,
            )
        )
    return InstallCacheSchema(total_bytes=total, entries=entries)


def _remove_cache_dir(directory: Path) -> int:
    """Delete one cache directory and its session row (when it has one).
    Returns the bytes freed, or -1 when the session is still running."""
    if not directory.name.isdigit():
        return 0
    session = db_install_session_handler.get_session(int(directory.name))
    if session is not None and session.state in RUNNING_INSTALL_STATES:
        return -1
    freed = dir_size_bytes(directory)
    clear_session_cache(int(directory.name))
    if session is not None:
        db_install_session_handler.delete_session(session.id)
    return freed


@protected_route(
    router.get,
    "/install/cache",
    [Scope.PLATFORMS_WRITE],
)
async def get_install_cache(request: Request) -> InstallCacheSchema:
    """Every install cache on disk with its size and age, plus the total.

    Backs the Settings cache manager. Covers all users' installs, hence the
    admin-level scope.
    """
    return await run_in_threadpool(_build_cache_listing)


@protected_route(
    router.delete,
    "/install/cache/{session_id}",
    [Scope.PLATFORMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_install_cache_entry(
    request: Request,
    session_id: Annotated[int, PathVar(description="Install session id.", ge=1)],
) -> InstallCacheClearSchema:
    """Delete one install cache (and its session). Refuses (409) while the
    install is still running."""
    directory = session_cache_dir(session_id)
    session = db_install_session_handler.get_session(session_id)
    if session is None and not directory.is_dir():
        raise InstallSessionNotFoundException(session_id)
    if session is not None and session.state in RUNNING_INSTALL_STATES:
        raise InstallSessionRunningException(session.rom_id)
    freed = await run_in_threadpool(_remove_cache_dir, directory)
    return InstallCacheClearSchema(removed=1, freed_bytes=max(freed, 0), skipped=0)


@protected_route(
    router.delete,
    "/install/cache",
    [Scope.PLATFORMS_WRITE],
)
async def delete_all_install_caches(request: Request) -> InstallCacheClearSchema:
    """Delete every install cache, leaving running installs alone."""

    def _run() -> InstallCacheClearSchema:
        removed = skipped = freed_total = 0
        for directory in cache_root_dirs():
            freed = _remove_cache_dir(directory)
            if freed < 0:
                skipped += 1
            else:
                removed += 1
                freed_total += freed
        return InstallCacheClearSchema(
            removed=removed, freed_bytes=freed_total, skipped=skipped
        )

    return await run_in_threadpool(_run)


# Request headers that must never be forwarded upstream (RFC 7230 6.1
# hop-by-hop headers, plus Host/Content-Length which are wrong once the
# target host/body framing changes, and our own auth headers, which the
# install-worker has no use for and shouldn't see).
_VNC_PROXY_DROP_REQUEST_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "cookie",
    "authorization",
}
# Response headers that must never be echoed back to the client for the
# same reason (aiohttp/Starlette manage framing and connection state
# themselves; letting the upstream's values through corrupts both) - plus
# Server/Date, which our own response object sets itself, so passing the
# upstream's through as well would just duplicate them.
_VNC_PROXY_DROP_RESPONSE_HEADERS = _VNC_PROXY_DROP_REQUEST_HEADERS | {
    "content-encoding",
    "server",
    "date",
}


def _assert_owns_vnc_port(user_id: int, port: int) -> None:
    """Confirm ``user_id`` actually owns the install running its VNC bridge
    on ``port`` before proxying anything through to it - the sandbox
    worker's HTTP/WS server itself has no auth of its own."""
    session = db_install_session_handler.get_running_session_for_user_port(
        user_id, port
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


@protected_route(
    router.get,
    "/install/vnc/{port}/{path:path}",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_403_FORBIDDEN: {}},
)
async def install_vnc_http(
    request: Request,
    port: Annotated[int, PathVar(ge=1, le=65535)],
    path: str,
) -> Response:
    """Proxy the noVNC static page/assets for a running install's VNC bridge
    through to the install-worker, gated on the owning user's session. The
    actual VNC pixel data goes over install_vnc_ws instead; this only ever
    serves vnc.html and its JS/CSS.
    """
    _assert_owns_vnc_port(request.user.id, port)

    upstream_url = f"http://{INSTALL_WORKER_HOST}:{port}/{path}"
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _VNC_PROXY_DROP_REQUEST_HEADERS
    }

    # The shared per-request session from utils/context.py, not a fresh
    # ClientSession per call - this proxy is hit once per noVNC asset, and a
    # new session (and its own connection pool) for each would add needless
    # connection/TLS-handshake churn.
    session = ctx_aiohttp_session.get()
    try:
        upstream_response = await session.request(
            request.method,
            upstream_url,
            params=list(request.query_params.multi_items()),
            headers=forward_headers,
            data=await request.body(),
        )
    except aiohttp.ClientError as e:
        raise InstallWorkerUnavailableException() from e

    async def body_stream():
        try:
            async for chunk in upstream_response.content.iter_any():
                yield chunk
        finally:
            upstream_response.close()

    response_headers = {
        k: v
        for k, v in upstream_response.headers.items()
        if k.lower() not in _VNC_PROXY_DROP_RESPONSE_HEADERS
    }
    # noVNC static assets are small and only change when the worker image
    # is rebuilt — but a stale browser cache of an older ui.js/vnc.html
    # (e.g. from a different noVNC version) causes confusing crashes like
    # "Cannot read properties of null (reading 'addEventListener')" because
    # the cached JS references DOM elements the cached HTML doesn't define.
    response_headers["Cache-Control"] = "no-store"
    return StreamingResponse(
        body_stream(),
        status_code=upstream_response.status,
        headers=response_headers,
        media_type=upstream_response.content_type,
    )


# protected_route can't be used here: it injects FastAPI Security()
# dependencies (OAuth2PasswordBearer, HTTPBasic) meant for HTTP requests,
# which crash with a TypeError when resolved for a websocket connection (no
# Request to give them). requires() alone is what actually enforces the
# scope for either kind of route (see decorators/auth.py and
# starlette.authentication.requires' own websocket/request branching) - a
# bearer/basic Authorization header isn't usable from a websocket handshake
# in a browser anyway, so nothing is lost; cookie-session auth (the normal
# case for a same-origin page like the VNC overlay) still applies.
@router.websocket("/install/vnc/{port}/{path:path}")
@requires([Scope.ROMS_INSTALL])
async def install_vnc_ws(
    websocket: WebSocket,
    port: Annotated[int, PathVar(ge=1, le=65535)],
    path: str,
) -> None:
    """Proxy the actual VNC websocket (binary RFB-over-websocket frames via
    websockify on the install-worker) for a running install, gated on the
    owning user's session. See install_vnc_http for the static page/assets.
    """
    try:
        _assert_owns_vnc_port(websocket.user.id, port)
    except HTTPException:
        await websocket.close(code=4403)
        return

    requested_protocols = [
        p.strip()
        for p in (websocket.headers.get("sec-websocket-protocol") or "").split(",")
        if p.strip()
    ]
    # The install-sandbox's websockify serves static files at specific paths
    # (vnc.html, JS, CSS) but accepts WebSocket connections at /websockify.
    # The `path` parameter here includes the proxy prefix (e.g. api/roms/install/vnc/6900/websockify)
    # which websockify doesn't know about. Strip to just the websockify endpoint.
    upstream_url = f"ws://{INSTALL_WORKER_HOST}:{port}/websockify"

    # utils/context.py's shared session, reached directly from app.state:
    # set_context_middleware (and the ctx_aiohttp_session var it populates)
    # only runs for the HTTP request/response cycle, not for a websocket
    # connection, so ctx_aiohttp_session.get() would raise here instead of
    # returning it - this is the same underlying ClientSession either way.
    session = websocket.app.state.aiohttp_session
    try:
        async with session.ws_connect(
            upstream_url,
            params=list(websocket.query_params.multi_items()),
            protocols=requested_protocols or (),
        ) as upstream:
            await websocket.accept(subprotocol=upstream.protocol)

            async def client_to_upstream():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("bytes") is not None:
                        await upstream.send_bytes(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream.send_str(message["text"])

            async def upstream_to_client():
                async for message in upstream:
                    if message.type == aiohttp.WSMsgType.BINARY:
                        await websocket.send_bytes(message.data)
                    elif message.type == aiohttp.WSMsgType.TEXT:
                        await websocket.send_text(message.data)
                    else:
                        return

            first_done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except aiohttp.ClientError:
        log.debug(f"Couldn't reach install-worker VNC bridge on port {port}")
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()


@protected_route(
    router.get,
    "/{id}/install/files",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_install_files(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    session_id: int | None = None,
) -> InstallFilesSchema:
    """List the files a finished install produced, with their sha1 hashes.

    A client downloads each one from GET .../install/files/{path} and
    compares the hash against its own copy to catch a corrupted transfer.
    404s until the session reaches a state that actually wrote a manifest
    (DONE; a run that FAILED partway never gets one). Pass `session_id` to
    pin to a specific attempt (see `_resolve_session`).
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)

    entries = read_manifest(session_cache_dir(session.id))
    if entries is None:
        raise InstallSessionNotFoundException(id)

    return InstallFilesSchema(
        rom_id=rom.id,
        total_bytes=manifest_total_bytes(entries),
        files=[
            InstallFileSchema(path=e.path, size_bytes=e.size_bytes, sha1=e.sha1)
            for e in entries
        ],
    )


@protected_route(
    router.get,
    "/{id}/install/files/{file_path:path}",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def download_install_file(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_path: str,
    device_id: str = "web",
    session_id: int | None = None,
) -> Response:
    """Download one file from a finished install.

    `file_path` must be an exact entry in the session's manifest: anything
    else 404s before ever touching the filesystem, so this can't be used to
    read outside the session's own cache directory. Pass `session_id` to pin
    to a specific attempt (see `_resolve_session`).
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)

    entries = read_manifest(session_cache_dir(session.id))
    entry = find_manifest_entry(entries, file_path) if entries else None
    if not entry:
        raise InstallSessionNotFoundException(id)

    await stream_presence.heartbeat(session.id, request.user.id, device_id)

    if DEV_MODE:
        return FileResponse(
            path=session_cache_dir(session.id) / entry.path,
            filename=Path(entry.path).name,
            media_type="application/octet-stream",
        )

    return FileRedirectResponse(
        download_path=Path(f"/cache/installs/{session.id}/{entry.path}"),
        filename=Path(entry.path).name,
    )


@protected_route(
    router.get,
    "/{id}/install/download",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def download_install_cache(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    session_id: int | None = None,
) -> Response:
    """Download a finished install's entire cache as a single ZIP.

    Only available once the session reaches DONE, same gate as
    `GET /install/files` (whose entries this packages together instead of
    serving one at a time). Pass `session_id` to pin to a specific attempt
    (see `_resolve_session`).

    Streams via nginx's mod_zip module (see utils.nginx.ZipResponse) - the
    exact mechanism `GET /roms/download` already uses for bulk ROM
    downloads - so a multi-GB install cache is never buffered into memory
    or built to a temp file here, just referenced by its already-on-disk
    location. DEV_MODE (no nginx in front to interpret mod_zip headers)
    falls back to a real in-memory ZIP, matching the equivalent dev-mode
    fallback for bulk ROM downloads.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)

    entries = read_manifest(session_cache_dir(session.id))
    if not entries:
        raise InstallSessionNotFoundException(id)

    zip_filename = f"{rom.fs_name} - Install Cache.zip"

    if DEV_MODE:
        cache_dir = session_cache_dir(session.id)
        ensure_zipfile_writable()
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for entry in entries:
                zf.write(cache_dir / entry.path, arcname=entry.path)
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f"attachment; filename*=UTF-8''{quote(zip_filename)}"
                ),
            },
        )

    return ZipResponse(
        content_lines=[
            ZipContentLine(
                crc32=None,
                size_bytes=entry.size_bytes,
                encoded_location=quote(f"/cache/installs/{session.id}/{entry.path}"),
                filename=entry.path,
            )
            for entry in entries
        ],
        filename=zip_filename,
    )


# Network-write granularity for the still-running-install streaming path
# below - decoupled from manifest.CHUNK_SIZE (the hashing/repair unit), just
# how much we read+throttle+yield at a time.
_STREAM_PIECE_SIZE = 256 * 1024


def _parse_range(
    range_header: str | None, sealed_bytes: int
) -> tuple[int, int] | tuple[None, None]:
    """Clamp a Range request to the hash-verified prefix of a still-growing
    file (``[0, sealed_bytes)``). No Range header defaults to serving from
    the start. ``(None, None)`` means nothing sealed is left to give for the
    requested range - the caller responds 416, and a client's own retry/
    backoff loop naturally waits for more of the file to seal."""
    start = 0
    end = sealed_bytes - 1
    if range_header and range_header.startswith("bytes="):
        spec = range_header[len("bytes=") :].split(",")[0].strip()
        range_start, _, range_end = spec.partition("-")
        if range_start:
            try:
                start = int(range_start)
            except ValueError:
                start = 0
        if range_end:
            try:
                end = min(end, int(range_end))
            except ValueError:
                pass
    if sealed_bytes <= 0 or start > end:
        return None, None
    return start, end


@protected_route(
    router.get,
    "/{id}/install/stream/manifest",
    [Scope.ROMS_INSTALL],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_install_stream_manifest(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    session_id: int | None = None,
) -> InstallStreamManifestSchema:
    """Live view of an install's output, whether it's still running or
    already finished - lets the Install page poll ONE endpoint regardless
    of state.

    While the install is running, entries come from the best-effort live
    manifest (see handler.install.manifest.scan_live_manifest); once it's
    DONE, the same shape is synthesized from the real, fully-verified
    manifest instead, so a completed session's files never look different
    to a client just because it stopped polling and came back.

    Pass `session_id` (the id a client already got back from starting or
    discovering its own attempt) to keep reading that exact attempt's cache
    even if a newer one for the same ROM starts in the meantime - see
    `_resolve_session`. Omit it to just get the latest, as before.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)

    cache_dir = session_cache_dir(session.id)
    live_entries = read_live_manifest(cache_dir)
    if live_entries is None:
        final_entries = read_manifest(cache_dir)
        if final_entries is None:
            raise InstallSessionNotFoundException(id)
        live_entries = live_view_of_final_manifest(final_entries)

    return InstallStreamManifestSchema(
        rom_id=rom.id,
        files=[
            InstallStreamFileSchema(
                path=e.path,
                size_bytes=e.size_bytes,
                sealed_bytes=e.sealed_bytes,
                complete=e.complete,
            )
            for e in live_entries.values()
        ],
        viewer_count=await stream_presence.count_viewers(session.id),
        download_speed_limit_bytes_per_sec=await bandwidth.get_bytes_per_second(),
    )


@protected_route(
    router.get,
    "/{id}/install/stream/{file_path:path}",
    [Scope.ROMS_INSTALL],
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_416_RANGE_NOT_SATISFIABLE: {},
    },
)
async def download_install_stream_file(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_path: str,
    device_id: str = "web",
    session_id: int | None = None,
) -> Response:
    """Download one file from an install, live if it's still running.

    Once the file is complete this behaves exactly like
    GET .../install/files/{path} (same code path, unchanged - nginx/
    FileResponse Range support applies as always). While it's still being
    written, this instead serves a Range request clamped to the sealed
    (hash-verified) portion so far: a request past what's sealed yet gets
    416, and any browser's or download manager's own retry/backoff loop
    naturally waits for more of the file to seal before trying again -
    that's the whole resume story, no session/token state needed for it.

    `file_path` must be an exact live- or final-manifest entry, same
    traversal guard as the existing download endpoint. Pass `session_id` to
    pin to a specific attempt (see `_resolve_session`) - a streaming client
    should always pass the id of the session it's actually downloading from,
    so a fresh, unrelated install attempt for the same ROM (a different
    client, or the same one pressing Install again) can't yank it onto an
    empty session and 404 it mid-download.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)
    assert_rom_visible(request, rom)

    session = _resolve_session(rom.id, request.user.id, session_id)
    if not session:
        raise InstallSessionNotFoundException(id)

    cache_dir = session_cache_dir(session.id)
    live_entries = read_live_manifest(cache_dir)
    entry = live_entries.get(file_path) if live_entries else None

    if entry is None:
        # No live manifest at all (install already finished) or this path
        # was never part of it - either way, defer to the exact existing
        # "complete file" path, unchanged.
        final_entries = read_manifest(cache_dir)
        final_entry = (
            find_manifest_entry(final_entries, file_path) if final_entries else None
        )
        if not final_entry:
            raise InstallSessionNotFoundException(id)

        await stream_presence.heartbeat(session.id, request.user.id, device_id)

        if DEV_MODE:
            return FileResponse(
                path=cache_dir / final_entry.path,
                filename=Path(final_entry.path).name,
                media_type="application/octet-stream",
            )
        return FileRedirectResponse(
            download_path=Path(f"/cache/installs/{session.id}/{final_entry.path}"),
            filename=Path(final_entry.path).name,
        )

    start, end = _parse_range(request.headers.get("range"), entry.sealed_bytes)
    if start is None:
        return Response(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            headers={"Retry-After": "1"},
        )

    await stream_presence.heartbeat(session.id, request.user.id, device_id)

    file_on_disk = cache_dir / entry.path
    content_length = end - start + 1

    async def body_stream():
        # Reads happen in a thread (asyncio.to_thread, matching the pattern
        # already used for other blocking file/hash work in this codebase,
        # e.g. handler/filesystem/roms_handler.py) - a plain sync read here
        # would block the event loop for every other request while this
        # multi-GB file is served.
        remaining = content_length
        f = await asyncio.to_thread(file_on_disk.open, "rb")
        try:
            await asyncio.to_thread(f.seek, start)
            while remaining > 0:
                piece = await asyncio.to_thread(
                    f.read, min(remaining, _STREAM_PIECE_SIZE)
                )
                if not piece:
                    break
                await bandwidth.acquire(len(piece))
                remaining -= len(piece)
                yield piece
        finally:
            await asyncio.to_thread(f.close)

    return StreamingResponse(
        body_stream(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type="application/octet-stream",
        headers={
            "Content-Range": f"bytes {start}-{end}/*",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
        },
    )
