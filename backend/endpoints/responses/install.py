from __future__ import annotations

from pydantic import ConfigDict

from models.install_session import InstallSessionState

from .base import BaseModel, UTCDatetime


class InstallCandidateSchema(BaseModel):
    """A possible installer/entry file detected inside a ROM's directory."""

    # Path relative to the ROM's directory.
    path: str
    file_name: str
    file_size_bytes: int
    # Detection bucket, lower rank = higher priority (see installer_detection.py).
    rank: int
    # Human-readable reason this file was picked (e.g. "gog installer", "archive").
    kind: str


class InstallCandidatesSchema(BaseModel):
    rom_id: int
    candidates: list[InstallCandidateSchema]
    # True when nothing could be auto-detected and the client must prompt a picker.
    needs_manual_pick: bool
    # True when the ROM is not an installer and should be stream-copied directly.
    stream_copy: bool


class InstallFileSchema(BaseModel):
    """One file produced by a finished install, downloadable and verifiable."""

    # Path relative to the session's cache directory; also the path segment
    # used by GET /{id}/install/files/{path} to download it.
    path: str
    size_bytes: int
    sha1: str


class InstallFilesSchema(BaseModel):
    rom_id: int
    total_bytes: int
    files: list[InstallFileSchema]


class ProtonBuildSchema(BaseModel):
    """One Proton build the server knows about (see handler.install.proton_builds).

    Installed builds are discovered at runtime by the ProtonBuildManager scanning
    PROTON_INSTALL_ROOT (or legacy env vars) for an executable binary. Non-installed
    builds come from upstream release APIs (GE-Proton, Proton-CachyOS) and can be
    downloaded at runtime via POST /install/proton/{id}/download.
    """

    id: str
    label: str
    # Whether this build's binary actually exists on disk right now.
    installed: bool
    # Human-readable version string from the upstream release (e.g. "10-34").
    version: str | None = None
    # Where this build lives on disk, if installed.
    path: str | None = None
    # "runtime" = discovered on disk, "upstream" = only downloadable.
    source: str = "runtime"
    # Approximate tarball size in bytes, only for upstream builds.
    size_bytes: int | None = None
    # Added by the user from Settings (can be removed again).
    custom: bool = False


class ProtonBuildsSchema(BaseModel):
    builds: list[ProtonBuildSchema]


class ProtonDownloadResponseSchema(BaseModel):
    """Response to POST /install/proton/{build_id}/download — the RQ job id
    to poll for completion via GET /install/proton/{build_id}/progress."""

    job_id: str


class ProtonDownloadProgressSchema(BaseModel):
    """Progress of an in-flight Proton download/extract (0.0–1.0).

    ``progress`` is the download fraction while the tarball streams. Once the
    download completes and extraction begins, ``extracting`` flips to true and
    ``progress`` resets to 0.0 so the client can show an indeterminate
    "Installing Proton…" spinner instead of a stale 100 %. None when no
    download/extract is running for this build_id (either never started, or
    finished and cleaned up).
    """

    progress: float | None = None
    extracting: bool = False


class InstallWorkerStatusSchema(BaseModel):
    """Whether an install-sandbox worker is currently connected.

    Drives whether the client offers the "Install" action at all - there's no
    separate on/off setting, availability is purely "is a worker listening
    right now" (see handler.install.queue_status.has_install_worker).
    """

    available: bool


class InstallSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rom_id: int
    user_id: int
    state: InstallSessionState
    installer_path: str | None = None
    # Archive/disc image the installer comes from, when it isn't run directly.
    source_path: str | None = None
    # "extracting" / "mounting" while the worker unpacks source_path (see
    # models.install_session.InstallPhase), with the file name in
    # phase_detail. None once the installer window is up or when not applicable.
    phase: str | None = None
    phase_detail: str | None = None
    proton_build: str | None = None
    expires_at: UTCDatetime | None = None
    # Experimental auto mode (OCR clicks through the installer's dialogs).
    # auto_status is "running" or "needs_manual" (auto mode found nothing it
    # can press: the user should continue by hand through the VNC page);
    # auto_detail is its last action. Both None while auto mode is off.
    auto_mode: bool = False
    # Per-install manual mode override (forces AWAITING_INSTALLER even when
    # candidates exist so the user can pick the installer themselves).
    manual_mode: bool = False
    auto_status: str | None = None
    auto_detail: str | None = None
    vnc_url: str | None = None
    bytes_written: int
    bytes_total: int
    error: str | None = None
    created_at: UTCDatetime
    updated_at: UTCDatetime
    # Set only while state is AWAITING_INSTALLER: no client (any of them, not
    # just this one) could confidently auto-pick an installer, so a human has
    # to - this is where. "Manual mode", as opposed to the OCR-driven auto mode.
    # Not a DB column - filled in by the endpoint, not from_attributes.
    manual_install_url: str | None = None


class InstallDashboardEntrySchema(BaseModel):
    """One row for the Home "Active Installers" widget: a session plus just
    enough of its ROM to render and link to it."""

    session: InstallSessionSchema
    rom_id: int
    rom_name: str | None
    platform_slug: str
    path_cover_small: str | None


class InstallDashboardSchema(BaseModel):
    entries: list[InstallDashboardEntrySchema]


class InstallStreamFileSchema(BaseModel):
    """One file's live delivery state - how much exists, how much of that
    is safe to download right now, and whether it's actually done (see
    handler.install.manifest.scan_live_manifest for what "safe" means here -
    a stable-for-one-scan prefix, not a hash-verified one; the install's
    own single whole-file sha1 is what actually gets verified, once)."""

    path: str
    size_bytes: int
    sealed_bytes: int
    complete: bool


class InstallStreamManifestSchema(BaseModel):
    """Polled by the Install page regardless of session state - entries come
    from the best-effort live manifest while installing, or are synthesized
    from the real one once DONE (see handler.install.manifest)."""

    rom_id: int
    files: list[InstallStreamFileSchema]
    # Other clients currently pulling this same session's files right now.
    viewer_count: int
    # The server-wide cap all of them share, or None when unlimited.
    download_speed_limit_bytes_per_sec: int | None = None


class InstallCacheEntrySchema(BaseModel):
    """One install cache directory on disk, for the Settings cache manager."""

    session_id: int
    rom_id: int
    rom_name: str | None
    platform_slug: str | None
    user_id: int
    state: InstallSessionState
    size_bytes: int
    created_at: UTCDatetime
    updated_at: UTCDatetime
    # NULL means the cache never expires.
    expires_at: UTCDatetime | None = None


class InstallCacheSchema(BaseModel):
    # Everything under the install cache root, including directories that no
    # session owns anymore.
    total_bytes: int
    entries: list[InstallCacheEntrySchema]


class InstallCacheClearSchema(BaseModel):
    removed: int
    freed_bytes: int
    # Caches left alone because their install is still running.
    skipped: int


class CustomProtonBuildForm(BaseModel):
    """A user-added Proton build: a display name and a tarball URL."""

    name: str
    url: str
