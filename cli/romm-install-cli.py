#!/usr/bin/env python3
"""romm-install-cli: minimal CLI client to drive RomM's stream-install feature.

Pure stdlib (urllib, json, argparse, sys). No third-party deps.

Usage:
python cli/romm-install-cli.py --base http://localhost:5100 \\
      --user admin --pass admin --rom-id 123 --out /tmp/installed

Just run it - the server does the rest, the same way it would for the web
UI's own "Install" button (single source of truth: POST /{romId}/install
resolves everything server-side, no client has to replicate the logic):
  - Already installed (a cache from a prior run is still on disk)? Streamed
    immediately, nothing is (re)installed.
  - Not installed? The server starts it exactly as the web Install page's
    button would: top-ranked candidate, and for an archive or disc image it
    unpacks it and picks the executable inside (progress shows as
    "extracting <file>" / "mounting <file>"). No interaction needed to start.
  - No candidate at all - "manual mode": nobody (human or, someday, an
    OCR-driven "auto mode") can say which file to run. The session sits in
    AWAITING_INSTALLER and the response carries `manual_install_url` - this
    CLI prints it and stops; open it in a browser, finish the install there
    (the VNC session), then just re-run this same command to stream the
    result.

Flow:
  1. login (HTTP Basic, sent again on every later request; no session cookie
     is kept, so nothing here ever needs a CSRF token)
  2. GET /api/roms/{romId}/install - already DONE? skip straight to step 5,
     no worker needed at all
  3. GET /api/roms/{romId}/install/candidates (informational only - the
     server does its own auto-pick, this is just to print the options)
  4. POST /api/roms/{romId}/install {installer_path, proton_build, ttl_seconds}
     - installer_path is optional; omit it and let the server decide.
     AWAITING_INSTALLER in the response means manual mode - stop and print
     `manual_install_url` (this outcome never touches the worker at all). A
     transient 503 (worker not connected yet) is retried for ~50s instead of
     failing outright, same as the web UI's own "Install" button.
  5. poll GET /api/roms/{romId}/install/stream/manifest every 3s, started in
     a background thread concurrently with step 6's own polling - designed
     to work *while* an install is still running too (that's the whole
     "stream install" point), not just once it's DONE, though only the
     finished-install path has actually been verified end-to-end so far
  6. poll GET /api/roms/{romId}/install every 3s until state != active
  7. stream each file via Range GET /api/roms/{romId}/install/stream/{path}
  8. cancel: POST /api/roms/{romId}/install/cancel
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

POLL_INTERVAL = 3
MANIFEST_INTERVAL = 3
PROTON_POLL_INTERVAL = 2

# Distinguishes this CLI process from a browser tab (or another CLI run) in
# the server's own "N viewers currently downloading" presence tracking (see
# handler.install.stream_presence) - without a distinct id here, every CLI
# invocation would collapse into the same default "web" device and undercount
# concurrent downloaders, since that presence system counts per (user,
# device_id) pair specifically to tell separate clients apart.
DEVICE_ID = f"cli-{uuid.uuid4().hex[:8]}"

# A freshly (re)started install-sandbox worker takes real, bounded time to
# come up (Wine/Proton warmup then Redis registration) before POST /install
# can enqueue anything onto it - mirrors the web UI's own
# withWorkerStartupRetry (frontend/src/v2/composables/useInstallSession).
# ~50s total. Only matters for the auto-pick path that actually enqueues a
# job - a manual-mode result (AWAITING_INSTALLER) never touches the worker.
WORKER_STARTUP_RETRY_DELAYS = [2, 3, 5, 5, 5, 10, 10, 10]

ACTIVE_STATES = {"detecting", "awaiting_installer", "installing", "streaming"}


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr, flush=True)


def basic_header(user: str, pw: str) -> str:
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return f"Basic {token}"


class Client:
    def __init__(self, base: str, user: str, pw: str, timeout: float = 30.0):
        self.base = base.rstrip("/")
        self.user = user
        self.pw = pw
        self.timeout = timeout

    def _headers(self, extra: dict | None = None) -> dict:
        # Basic auth on every request, never a session cookie: RomM's CSRF
        # middleware only exempts a request from needing a CSRF token while
        # it resolves as Basic-authenticated. Sending back the romm_session
        # cookie the server sets on login would make it resolve as
        # session-authenticated instead, and then reject every POST/DELETE
        # with "CSRF token verification failed" since this CLI never has a
        # CSRF token to send.
        h = {"Accept": "application/json", "User-Agent": "romm-install-cli/1.0"}
        if self.user and self.pw:
            h["Authorization"] = basic_header(self.user, self.pw)
        if extra:
            h.update(extra)
        return h

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict | None = None,
        raw: bool = False,
        timeout: float | None = None,
    ) -> tuple[int, bytes, dict]:
        url = self.base + path
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers = headers or {}
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=data, method=method, headers=self._headers(headers)
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                content = resp.read()
                return resp.status, content, dict(resp.headers)
        except urllib.error.HTTPError as e:
            content = e.read()
            return e.code, content, dict(e.headers)
        except urllib.error.URLError as e:
            raise RuntimeError(f"connection error: {e}") from e

    def get_json(self, path: str, **kw) -> tuple[int, dict]:
        status, content, _ = self.request("GET", path, **kw)
        try:
            return status, json.loads(content.decode() or "null")
        except json.JSONDecodeError:
            return status, {"_raw": content.decode(errors="replace")}

    def post_json(self, path: str, body: dict, **kw) -> tuple[int, dict]:
        status, content, _ = self.request("POST", path, body=body, **kw)
        try:
            return status, json.loads(content.decode() or "null")
        except json.JSONDecodeError:
            return status, {"_raw": content.decode(errors="replace")}

    def delete_json(self, path: str, **kw) -> tuple[int, dict]:
        status, content, _ = self.request("DELETE", path, **kw)
        try:
            return status, json.loads(content.decode() or "null")
        except json.JSONDecodeError:
            return status, {"_raw": content.decode(errors="replace")}


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PiB"


def bar(pct: float, width: int = 30) -> str:
    filled = int(width * max(0.0, min(1.0, pct)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


_UNSAFE_DIRNAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def safe_dirname(name: str) -> str:
    """A ROM's display name, made safe to use as a single local directory
    component - strips characters that are path separators or otherwise
    reserved on common filesystems (mainly a Windows-host concern, since
    `name` itself is free text with no such restriction), and falls back to
    something non-empty if that leaves nothing usable."""
    cleaned = _UNSAFE_DIRNAME_CHARS.sub("_", name).strip(" .")
    return cleaned or "game"


def extract_error(content: bytes, status: int) -> str:
    try:
        data = json.loads(content.decode() or "null")
    except Exception:
        return f"HTTP {status}: {content.decode(errors='replace')[:300]}"
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, dict):
            return f"HTTP {status}: {detail.get('msg', detail)}"
        if detail:
            return f"HTTP {status}: {detail}"
        return f"HTTP {status}: {data}"
    return f"HTTP {status}: {content.decode(errors='replace')[:300]}"


class ApiError(RuntimeError):
    """A RuntimeError that also carries the HTTP status code, so a caller can
    react to a specific status (e.g. 503 = install worker not connected yet,
    worth retrying) without parsing the message text."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class RommClient:
    def __init__(self, c: Client):
        self.c = c

    # -- auth / discovery -------------------------------------------------
    def login(self) -> bool:
        status, content, _ = self.c.request("POST", "/api/login")
        if status not in (200, 204, 303):
            warn(extract_error(content, status))
            return False
        log(f"logged in as {self.c.user}")
        return True

    def rom_info(self, rom_id: int) -> dict:
        status, data = self.c.get_json(f"/api/roms/{rom_id}")
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    def candidates(self, rom_id: int) -> dict:
        status, data = self.c.get_json(f"/api/roms/{rom_id}/install/candidates")
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    def proton_builds(self) -> list:
        status, data = self.c.get_json("/api/roms/install/proton-builds")
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data.get("builds", [])

    def proton_download(self, build_id: str) -> str:
        status, data = self.c.post_json(
            f"/api/roms/install/proton/{build_id}/download", {}
        )
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data.get("job_id")

    def proton_progress(self, build_id: str) -> tuple[float | None, bool]:
        status, data = self.c.get_json(f"/api/roms/install/proton/{build_id}/progress")
        if status != 200:
            return None, False
        return data.get("progress"), bool(data.get("extracting", False))

    # -- session ----------------------------------------------------------
    def start_session(
        self,
        rom_id: int,
        installer_path: str | None,
        proton_build: str | None,
        ttl: int | None,
        auto_mode: bool | None = None,
        manual_mode: bool | None = None,
    ) -> dict:
        body = {"installer_path": installer_path, "proton_build": proton_build}
        if auto_mode is not None:
            body["auto_mode"] = auto_mode
        if manual_mode is not None:
            body["manual_mode"] = manual_mode
        if ttl is not None:
            body["ttl_seconds"] = ttl
        status, data = self.c.post_json(f"/api/roms/{rom_id}/install", body)
        if status not in (200, 201):
            raise ApiError(status, extract_error(json.dumps(data).encode(), status))
        return data

    def get_session(self, rom_id: int, session_id: int | None = None) -> dict:
        endpoint = f"/api/roms/{rom_id}/install"
        if session_id is not None:
            endpoint += f"?session_id={session_id}"
        status, data = self.c.get_json(endpoint)
        if status == 404:
            return {}
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    def cancel_session(self, rom_id: int) -> dict:
        status, data = self.c.post_json(f"/api/roms/{rom_id}/install/cancel", {})
        if status not in (200, 204):
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    def clear_cache(self, rom_id: int) -> dict:
        status, data = self.c.delete_json(f"/api/roms/{rom_id}/install")
        if status not in (200, 204):
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    # -- finished-install files (hash-verified) ---------------------------
    def list_files(self, rom_id: int, session_id: int | None = None) -> dict:
        """The finished install's own file list with sha1 hashes - only
        available once the session is DONE (see GET /install/files's own
        docstring). Used to verify a download actually matches what the
        server really produced, not just that it's the right size."""
        endpoint = f"/api/roms/{rom_id}/install/files"
        if session_id is not None:
            endpoint += f"?session_id={session_id}"
        status, data = self.c.get_json(endpoint)
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    def download_file(
        self, rom_id: int, path: str, session_id: int | None = None
    ) -> bytes:
        """Fetch one finished file in full (no Range) - used to re-download
        a file verify_and_repair found corrupted, not for the initial pull
        (stream_file already handles that, resumably, via the live endpoint).
        """
        encoded = urllib.parse.quote(path, safe="/")
        endpoint = f"/api/roms/{rom_id}/install/files/{encoded}"
        if session_id is not None:
            endpoint += f"?session_id={session_id}"
        status, content, _ = self.c.request("GET", endpoint, timeout=60.0)
        if status != 200:
            raise RuntimeError(extract_error(content, status))
        return content

    # -- streaming --------------------------------------------------------
    def stream_manifest(
        self, rom_id: int, session_id: int | None = None
    ) -> dict | None:
        """Live view of the install's output so far, or None if there's
        nothing to show yet.

        The backend 404s for two different reasons: no session exists at
        all, or one does but hasn't written any manifest yet (right after
        starting, or right after a fresh install was kicked off - see
        get_install_stream_manifest's own docstring). Either way, from a
        client streaming concurrently with the install, this just means
        "keep waiting" - not an error worth alarming anyone with.

        Pass `session_id` (the id this client is already streaming from) to
        stay pinned to that exact attempt - otherwise a fresh, unrelated
        install started for the same ROM (a different client, or pressing
        Install again after this one already finished) silently becomes
        "the latest session" server-side and yanks this poll onto an empty
        one, 404ing mid-download even though the files this client already
        has are still sitting there, complete, on disk.
        """
        endpoint = f"/api/roms/{rom_id}/install/stream/manifest"
        if session_id is not None:
            endpoint += f"?session_id={session_id}"
        status, data = self.c.get_json(endpoint)
        if status == 404:
            return None
        if status != 200:
            raise RuntimeError(extract_error(json.dumps(data).encode(), status))
        return data

    def stream_file(
        self,
        rom_id: int,
        path: str,
        out_dir: Path,
        speed_limit: int | None = None,
        session_id: int | None = None,
    ) -> int:
        """Range-stream whatever is currently available for one file,
        resuming from wherever the local copy left off. Returns the file's
        total size on disk after this call (not just what was added now).

        Deliberately never blocks waiting for *more* to become available -
        drains everything already sealed in a tight loop, then returns the
        moment there's nothing further right now (a 416, or a 206 with an
        empty body). The very first version of this internally slept and
        retried on exactly those cases instead, which meant one file the
        installer hadn't started writing yet (still 0 bytes) stalled the
        whole per-file loop in download_all_files forever - every other
        file in the same manifest, including ones already fully sealed and
        ready, never even got a chance to be requested. The caller's own
        manifest-repoll loop (MANIFEST_INTERVAL) is what retries a file
        that isn't ready yet, on its next pass through the whole list.
        """
        encoded = urllib.parse.quote(path, safe="/")
        params = {"device_id": DEVICE_ID}
        if session_id is not None:
            params["session_id"] = session_id
        endpoint = (
            f"/api/roms/{rom_id}/install/stream/{encoded}"
            f"?{urllib.parse.urlencode(params)}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)

        written = 0
        if dest.exists():
            written = dest.stat().st_size

        while True:
            headers = {}
            if written > 0:
                headers["Range"] = f"bytes={written}-"
            status, content, resp_headers = self.c.request(
                "GET", endpoint, headers=headers, timeout=60.0
            )
            if status in (200, 206):
                mode = "ab" if written > 0 else "wb"
                with open(dest, mode) as f:
                    f.write(content)
                written += len(content)
                if status == 200 and not headers.get("Range"):
                    return written
                cr = resp_headers.get("Content-Range") or resp_headers.get(
                    "content-range"
                )
                if cr and "/" in cr:
                    total_s = cr.rsplit("/", 1)[1]
                    if total_s.isdigit() and int(total_s) > 0:
                        if written >= int(total_s):
                            return written
                # 206 with nothing new this time - that's everything
                # currently available; stop here rather than wait for more.
                if len(content) == 0:
                    return written
                continue
            if status == 416:
                # Nothing sealed yet (or nothing beyond what we already
                # have) - not an error, just nothing more to give right now.
                return written
            raise RuntimeError(extract_error(content, status))


def download_all_files(
    rom: RommClient,
    rom_id: int,
    out_dir: Path,
    speed_limit: int | None = None,
    stop_event: threading.Event | None = None,
    session_id: int | None = None,
) -> int:
    """Poll manifest and stream every file to out_dir. Returns total bytes.

    Works the same whether the install is still running or already DONE -
    `stream/manifest` serves a best-effort live view while it's in progress
    (see handler.install.manifest) and the real, final one once it's not, so
    this loop just keeps polling either way until every listed file reports
    `complete`. That's what lets the caller start this concurrently with the
    install itself (a background thread) instead of waiting for it to
    finish first - the whole point of "stream install".

    `stop_event`, when given, is checked between polls so a caller running
    this in a background thread can ask it to give up early (e.g. the
    install failed - nothing more will ever seal) instead of retrying a
    dead session forever. A fresh one is used when not given, so the
    single-threaded (sequential, post-DONE) call site needs no special case.

    `session_id`, when given, pins every request to that exact session
    instead of "whatever's latest for this ROM" - without it, a fresh
    install attempt started for the same ROM in the meantime (a different
    client, or pressing Install again after this one already finished)
    would silently become "latest" server-side and yank this loop onto an
    empty session, 404ing mid-download even though every file already
    pulled down is sitting there, complete and correct, on disk.
    """
    stop_event = stop_event or threading.Event()
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    done_paths: set[str] = set()
    # Bytes already counted into `total` for each path so far, across
    # however many passes it's taken - stream_file now returns the file's
    # current on-disk size (not just what it added this call, since it no
    # longer blocks until a file is entirely done), so `total` has to track
    # the delta itself instead of just summing every return value.
    progress: dict[str, int] = {}
    last_manifest = 0.0
    last_logged: tuple[int, int] | None = None
    while not stop_event.is_set():
        now = time.time()
        if now - last_manifest < MANIFEST_INTERVAL and done_paths:
            if stop_event.wait(MANIFEST_INTERVAL - (now - last_manifest)):
                break
        last_manifest = time.time()
        try:
            manifest = rom.stream_manifest(rom_id, session_id=session_id)
        except RuntimeError as e:
            warn(str(e))
            if stop_event.wait(MANIFEST_INTERVAL):
                break
            continue
        if manifest is None:
            # Nothing to show yet - the install (or the sandbox job behind
            # it) hasn't written a single byte so far, totally normal right
            # after starting. Not an error, so no WARN - just wait and
            # check again next pass.
            if stop_event.wait(MANIFEST_INTERVAL):
                break
            continue
        files = manifest.get("files", [])
        viewers = manifest.get("viewer_count", 0)
        limit = manifest.get("download_speed_limit_bytes_per_sec") or speed_limit
        # Only when the count actually changes - printed every
        # MANIFEST_INTERVAL otherwise, drowning out everything else for an
        # install that runs minutes with nothing new sealed in between.
        current = (len(files), viewers)
        if current != last_logged:
            last_logged = current
            log(
                f"manifest: {len(files)} file(s), {viewers} viewer(s)"
                + (f", limit {fmt_bytes(limit)}/s" if limit else "")
            )
        new_done = 0
        for f in files:
            if stop_event.is_set():
                return total
            path = f["path"]
            size = f.get("size_bytes", 0)
            complete = f.get("complete", False)
            if path in done_paths:
                continue
            # Already have it in full from a previous run of this CLI (the
            # common case once "already installed" just re-streams a cache
            # every time) - skip the network round-trip entirely. Without
            # this, stream_file would ask for bytes past what's already on
            # disk and just get a 416 back for its trouble.
            local_path = out_dir / path
            if complete and local_path.is_file() and local_path.stat().st_size >= size:
                delta = size - progress.get(path, 0)
                total += delta
                progress[path] = size
                done_paths.add(path)
                new_done += 1
                continue
            # Grabs whatever is currently available and returns - does not
            # block waiting for more (see stream_file's own docstring for
            # why that matters: a file the installer hasn't started writing
            # yet must never stall every other file in this same pass).
            try:
                written = rom.stream_file(
                    rom_id, path, out_dir, speed_limit=limit, session_id=session_id
                )
            except RuntimeError as e:
                # A connection drop here would otherwise crash this
                # background thread with an unhandled traceback - the
                # server going away mid-download isn't something retrying
                # the very next file in this same pass can fix either, so
                # stop cleanly and let the caller's own poll loop notice.
                warn(str(e))
                return total
            delta = written - progress.get(path, 0)
            if delta > 0:
                log(
                    f"  streaming {path} ({fmt_bytes(written)} / {fmt_bytes(size)}"
                    + (" DONE" if complete and written >= size else ")")
                )
            total += delta
            progress[path] = written
            if complete and written >= size:
                done_paths.add(path)
                new_done += 1
            elif complete and written < size:
                # The install itself is fully done, yet this file's own
                # download still fell short - worth flagging, unlike a
                # plain "not sealed yet" shortfall mid-install.
                warn(f"  {path}: only got {fmt_bytes(written)} of {fmt_bytes(size)}")
        if files and new_done == 0 and all(f.get("complete") for f in files):
            log("all files complete")
            break
        if not files:
            if stop_event.wait(MANIFEST_INTERVAL):
                break
    return total


def _sha1_of(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_and_repair(
    rom: RommClient, rom_id: int, out_dir: Path, session_id: int | None = None
) -> None:
    """Verify every downloaded file's sha1 against the server's own
    finished, hash-verified manifest (GET /install/files) and re-fetch
    whatever doesn't match.

    This is the actual safety net behind the "Stream uncompleted files"
    experimental server setting (see Settings -> Library Management ->
    Stream Install): that setting lets the server hand out a growing file's
    bytes before it's confirmed to have stopped changing, so a client can
    end up with a local copy that's the right SIZE but not actually correct
    content. Comparing against the server's real manifest is what catches
    that - run unconditionally (not just when the experimental setting is
    known to be on) since it's cheap insurance either way and a client has
    no direct way to know what the server had it configured to.
    """
    try:
        manifest = rom.list_files(rom_id, session_id=session_id)
    except RuntimeError as e:
        warn(f"couldn't verify downloaded files: {e}")
        return

    files = manifest.get("files", [])
    log(f"verifying {len(files)} file(s) against the server's hashes...")
    mismatches = 0
    for entry in files:
        path = entry["path"]
        local_path = out_dir / path
        if not local_path.is_file():
            continue  # never downloaded (e.g. --no-download) - nothing to check
        if _sha1_of(local_path) == entry["sha1"]:
            continue
        mismatches += 1
        warn(f"  {path}: hash mismatch - re-downloading")
        try:
            local_path.write_bytes(
                rom.download_file(rom_id, path, session_id=session_id)
            )
            if _sha1_of(local_path) == entry["sha1"]:
                log(f"  {path}: repaired")
            else:
                warn(f"  {path}: still mismatched after re-download")
        except RuntimeError as e:
            warn(f"  {path}: repair failed: {e}")
    if mismatches == 0:
        log("all files verified OK")


def start_session_with_retry(
    rom: RommClient,
    rom_id: int,
    installer_path: str | None,
    proton_build: str | None,
    ttl: int | None,
    auto_mode: bool | None = None,
    manual_mode: bool | None = None,
) -> dict:
    """POST /install, riding out a transient "install worker not connected"
    503 instead of failing on it outright - same idea as the web UI's own
    withWorkerStartupRetry. A manual-mode result (AWAITING_INSTALLER) never
    raises this in the first place (the server returns it without ever
    checking the worker), so this only kicks in for the auto-pick path that
    actually needs to enqueue a job.

    Each attempt is a real POST /install, so the 503 (or lack of one) on
    every single retry reflects the server's own live has_install_worker()
    check, not a cached guess - there's no richer "what's it doing" signal
    to report while zero workers are registered (nothing is running yet to
    be busy doing anything), so this reports elapsed time/attempt count
    instead of pretending to know more. Once the worker registers and a
    session actually starts, poll_session takes over and shows real state
    (including Proton download/extract progress), same as the web UI.
    """
    start = time.time()
    for attempt, delay in enumerate([0, *WORKER_STARTUP_RETRY_DELAYS]):
        if delay:
            time.sleep(delay)
        try:
            return rom.start_session(
                rom_id, installer_path, proton_build, ttl, auto_mode, manual_mode
            )
        except ApiError as e:
            if e.status != 503 or attempt == len(WORKER_STARTUP_RETRY_DELAYS):
                raise
            elapsed = int(time.time() - start)
            warn(f"install worker not connected yet ({elapsed}s elapsed) - retrying...")
    raise AssertionError("unreachable")


def poll_session(
    rom: RommClient,
    rom_id: int,
    proton_build: str | None,
    timeout: float = 600.0,
    session_id: int | None = None,
) -> dict:
    """Poll session state until terminal or timeout. Prints progress.

    AWAITING_INSTALLER (server-side auto-pick couldn't confidently resolve
    an installer - "manual mode") is reported and returned immediately, not
    retried: nothing else is ever going to move this state along except a
    human finishing it through the web UI's VNC session, so waiting out any
    part of `timeout` here would just be dead time. `main()` normally
    catches this right after starting the session, before ever calling this
    function - the check stays here too for whoever calls this directly.

    `session_id` pins polling to that exact session (see download_all_files's
    own docstring for why) instead of whatever's latest for this ROM.
    """
    deadline = time.time() + timeout
    last_state = None
    announced_install_page = False
    last_phase = None
    last_auto_status = None
    install_page_url = f"{rom.c.base}/rom/{rom_id}/install"
    while time.time() < deadline:
        session = rom.get_session(rom_id, session_id=session_id)
        if not session:
            warn("no active session")
            time.sleep(POLL_INTERVAL)
            continue
        state = session.get("state")
        vnc_url = session.get("vnc_url")
        bytes_written = session.get("bytes_written", 0)
        bytes_total = session.get("bytes_total", 0)
        if state != last_state:
            log(f"state: {state}")
            last_state = state
        if state == "awaiting_installer":
            url = session.get("manual_install_url")
            warn("session needs a manual installer pick - finish it in a browser:")
            if url:
                log(f"  {url}")
            warn("re-run this CLI once it's running there to stream the result")
            return session
        if state in ACTIVE_STATES:
            phase, phase_detail = session.get("phase"), session.get("phase_detail")
            if phase and (phase, phase_detail) != last_phase:
                verb = "Mounting" if phase == "mounting" else "Extracting"
                log(f"  {verb} {phase_detail}")
                last_phase = (phase, phase_detail)
            if bytes_total:
                pct = bytes_written / bytes_total if bytes_total else 0.0
                log(f"  {bar(pct)} {fmt_bytes(bytes_written)}/{fmt_bytes(bytes_total)}")
            # Announced once, not every poll - it's the same link for the
            # life of the session. Points at the web Install page (not the
            # raw vnc_url iframe target, which carries a session-scoped
            # token meant for embedding, not for a human to open directly)
            # so the user can watch/drive the installer through the normal
            # UI once the VNC bridge comes up.
            if vnc_url and not announced_install_page:
                if session.get("auto_mode"):
                    log(
                        "  installer is running - auto mode is clicking through "
                        "it, watch or take over here:"
                    )
                else:
                    log(
                        "  installer is running - the wizard itself still needs "
                        "someone to click through it (or pass --auto-mode), "
                        "open this to do that:"
                    )
                log(f"  {install_page_url}")
                announced_install_page = True
            auto_status = session.get("auto_status")
            if auto_status != last_auto_status:
                if auto_status == "needs_manual":
                    warn(
                        "auto mode cannot continue - continue the installation "
                        f"by hand: {install_page_url}"
                    )
                elif auto_status == "running":
                    detail = session.get("auto_detail")
                    if detail:
                        log(f"  auto mode: {detail}")
                last_auto_status = auto_status
            # Proton download progress during bootstrapping. The session's
            # own `proton_build` (resolved server-side at creation time, see
            # resolve_effective_build) is the source of truth for which
            # build is actually in play - the `--proton-build` CLI flag is
            # usually omitted (letting the server auto-pick), so trusting
            # only that arg meant this branch almost never fired even while
            # the web UI's own Install page was showing real progress for
            # the exact same session.
            build_id = session.get("proton_build") or proton_build
            if build_id and state == "installing" and not vnc_url:
                prog, extracting = rom.proton_progress(build_id)
                if prog is not None:
                    label = "extracting" if extracting else "downloading"
                    log(f"  proton {build_id} {label} {bar(prog)} {prog * 100:.0f}%")
            time.sleep(POLL_INTERVAL)
            continue
        # terminal
        if state == "done":
            # Deliberately not "session DONE" or anything that reads as a
            # final word: this only means the server-side install itself
            # finished (every file already hashed and verified - see
            # _finalize_install) - a concurrent background download of a
            # large file can still be well behind that point locally. A
            # caller (or a human watching this output) that took a bare
            # "DONE" as "nothing left to do" and disconnected would silently
            # end up with a truncated local copy of whatever hadn't been
            # pulled yet.
            log(
                "install finished on the server (verified) - "
                "any files not yet downloaded locally are still being pulled"
            )
        elif state == "failed":
            warn(f"session FAILED: {session.get('error', '')}")
        elif state == "expired":
            warn("session EXPIRED")
        else:
            log(f"session state: {state}")
        return session
    warn("polling timed out")
    return rom.get_session(rom_id, session_id=session_id)


def main() -> int:
    p = argparse.ArgumentParser(description="RomM stream-install CLI client")
    p.add_argument(
        "--base", required=True, help="RomM base URL, e.g. http://localhost:5100"
    )
    p.add_argument("--user", default="admin")
    p.add_argument("--pass", dest="password", default="admin")
    p.add_argument("--rom-id", type=int, required=True)
    p.add_argument(
        "--installer-path",
        default=None,
        help="optional: relative path of installer inside the ROM dir, "
        "to override the server's own auto-pick. Usually not "
        "needed - omit it and let the server decide (or fall back "
        "to manual mode if it can't).",
    )
    p.add_argument(
        "--proton-build", default=None, help="proton build id (default: server)"
    )
    p.add_argument(
        "--mode",
        choices=["auto", "manual", "none"],
        default="none",
        help="experimental: override install mode for this run only - "
        "auto=OCR auto-click, manual=force manual picker, "
        "none=use server default (default: none)",
    )
    p.add_argument("--ttl", type=int, default=None, help="cache TTL seconds")
    p.add_argument(
        "--out",
        default="/tmp/romm-install",
        help="base output dir - files land under a subfolder named "
        "after the game, e.g. --out ~/roms -> "
        "~/roms/<game name>/...",
    )
    p.add_argument(
        "--no-download",
        action="store_true",
        help="start + poll, but do not stream files",
    )
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the post-download sha1 verification pass "
        "against the server's finished manifest",
    )
    p.add_argument(
        "--cancel",
        action="store_true",
        help="cancel an active session instead of starting",
    )
    p.add_argument("--clear", action="store_true", help="clear cache + session")
    p.add_argument(
        "--list-proton", action="store_true", help="list proton builds and exit"
    )
    p.add_argument(
        "--download-proton",
        default=None,
        help="download a proton build by id and watch progress",
    )
    p.add_argument("--timeout", type=float, default=900.0)
    args = p.parse_args()

    client = Client(args.base, args.user, args.password)
    rom = RommClient(client)

    try:
        return _run(args, rom)
    except RuntimeError as e:
        msg = str(e)
        if "connection error" in msg:
            warn(f"cannot reach {args.base} - is the RomM server running?")
        else:
            warn(msg)
        return 1
    except KeyboardInterrupt:
        warn("interrupted")
        return 130


def _run(args: argparse.Namespace, rom: RommClient) -> int:
    if not rom.login():
        return 1

    if args.list_proton:
        builds = rom.proton_builds()
        for b in builds:
            print(
                f"{b.get('id'):30s} installed={b.get('installed')} "
                f"version={b.get('version')} source={b.get('source')}"
            )
        return 0

    if args.download_proton:
        job_id = rom.proton_download(args.download_proton)
        log(f"proton download job: {job_id}")
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            prog, extracting = rom.proton_progress(args.download_proton)
            if prog is None:
                time.sleep(PROTON_POLL_INTERVAL)
                continue
            label = "extracting" if extracting else "downloading"
            log(f"  {label} {bar(prog)} {prog * 100:.0f}%")
            if prog >= 1.0 and not extracting:
                log("proton download complete")
                return 0
            time.sleep(PROTON_POLL_INTERVAL)
        warn("proton download timed out")
        return 1

    if args.clear:
        rom.clear_cache(args.rom_id)
        log("cache cleared")
        return 0

    if args.cancel:
        rom.cancel_session(args.rom_id)
        log("session cancelled")
        return 0

    # Files land under a per-game subfolder of --out (e.g. --out ~/roms +
    # "Jazz Jackrabbit 2" -> ~/roms/Jazz Jackrabbit 2/...), not dumped flat -
    # a manifest's own paths already carry whatever installer-specific
    # top-level folders happened to end up in it (a vendor folder like
    # "GOG Games", a stray "users/..." shortcut, ...), which isn't a name a
    # human picked for this game and gets confusing fast with more than one
    # ROM sharing the same --out.
    info = rom.rom_info(args.rom_id)
    game_name = info.get("name") or info.get("fs_name_no_ext") or f"rom-{args.rom_id}"
    out_dir = Path(args.out) / safe_dirname(game_name)

    # Step 1: already installed? A DONE session means its cache is still on
    # disk - stream straight from it, no worker/candidates/start needed at
    # all (see start_install_session's own docstring for why POSTing here
    # would just hand the same session back anyway; skipping the POST
    # entirely also means an already-cached game can still be streamed even
    # if the install worker itself isn't running right now).
    existing = rom.get_session(args.rom_id)
    if existing and existing.get("state") == "done":
        log(
            f"already installed: session id={existing.get('id')} - streaming cached files"
        )
        session = existing
    else:
        cands = rom.candidates(args.rom_id)
        log(
            f"candidates: {len(cands.get('candidates', []))} "
            f"needs_manual_pick={cands.get('needs_manual_pick')} "
            f"stream_copy={cands.get('stream_copy')}"
        )
        for c in cands.get("candidates", []):
            log(
                f"  - {c['file_name']} ({fmt_bytes(c['file_size_bytes'])}) "
                f"rank={c['rank']} kind={c['kind']}"
            )

        # Step 2: --installer-path stays a supported override, but is no
        # longer required - omit it and the server auto-picks the same way
        # the web UI's own "Install" button does (see
        # start_install_session's docstring). Only a genuinely ambiguous
        # pick falls back to "manual mode", handled below. A transient 503
        # (worker not connected yet) is retried, not a hard failure - manual
        # mode itself never needs the worker at all, so this only ever
        # matters when the server can auto-pick and needs to enqueue a job.
        if args.mode == "auto":
            auto_mode, manual_mode = True, False
        elif args.mode == "manual":
            auto_mode, manual_mode = False, True
        else:
            auto_mode, manual_mode = None, False
        session = start_session_with_retry(
            rom,
            args.rom_id,
            args.installer_path,
            args.proton_build,
            args.ttl,
            auto_mode,
            manual_mode,
        )
        log(f"session started: id={session.get('id')} state={session.get('state')}")

        # Step 3: manual mode - the server couldn't confidently resolve an
        # installer (or, for a title that needs it, nobody has clicked
        # through the installer's own dialogs yet). Send the human to the
        # web UI's VNC session and stop - nothing here can finish this.
        if session.get("state") == "awaiting_installer":
            url = session.get("manual_install_url")
            warn("this install needs a manual pick - finish it in a browser:")
            if url:
                log(f"  {url}")
            warn("re-run this CLI once it's running there to stream the result")
            return 1

    # Pinned from here on: every remaining call passes this exact session id
    # instead of letting the server resolve "whatever's latest for this ROM"
    # each time - otherwise a fresh, unrelated install attempt for the same
    # ROM (a different client, or pressing Install again once this one is
    # already done) would silently become "latest" server-side and yank this
    # very run onto an empty session mid-stream (see download_all_files's own
    # docstring for the full story).
    session_id = session.get("id")

    # Step 4: stream. Started concurrently with the install actually running
    # (a background thread), not after it finishes - "stream install" means
    # a client can already start pulling finished pieces of a file before
    # the whole install (and its final manifest) is done, see
    # download_all_files's own docstring. Skipped entirely for a session
    # already DONE only in the sense that there's nothing left to wait for -
    # download_all_files itself handles both cases identically.
    stop_event = threading.Event()
    stream_result: dict[str, int] = {}
    stream_thread: threading.Thread | None = None
    if not args.no_download:

        def _stream() -> None:
            stream_result["total"] = download_all_files(
                rom, args.rom_id, out_dir, stop_event=stop_event, session_id=session_id
            )

        stream_thread = threading.Thread(target=_stream, daemon=True)
        stream_thread.start()

    session = poll_session(
        rom, args.rom_id, args.proton_build, timeout=args.timeout, session_id=session_id
    )
    state = session.get("state")

    if stream_thread is not None:
        if state != "done":
            # failed/expired/timed out - nothing more will ever seal, don't
            # let the streaming loop keep retrying a dead session forever.
            stop_event.set()
            stream_thread.join(timeout=30.0)
        else:
            if stream_thread.is_alive():
                log(
                    "waiting for the local download to catch up "
                    "(server-side install already finished)..."
                )
            # Let it finish naturally (it stops on its own once every listed
            # file reports complete) - the overall --timeout budget doubles
            # as a safety net so this can't hang forever either.
            stream_thread.join(timeout=args.timeout)
        total = stream_result.get("total", 0)
        if state == "done":
            # This, not the earlier "install finished on the server" line,
            # is the actual "you have everything, safe to disconnect" signal
            # - the two can land many seconds (or, for one very large file
            # on a slow link, much longer) apart.
            log(
                f"all files downloaded ({fmt_bytes(total)}) to {out_dir} - install complete"
            )
            if not args.no_verify:
                verify_and_repair(rom, args.rom_id, out_dir, session_id=session_id)
    elif state == "done":
        log(
            "install done; files are cached on server, pass --no-download false to fetch"
        )

    if state == "failed":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
