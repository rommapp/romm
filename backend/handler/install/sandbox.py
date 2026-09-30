"""Build the bubblewrap command that isolates a server-side installer run.

The installer is untrusted code (arbitrary .exe/.msi/.bat), so it must never
run with the backend's privileges or filesystem view. This module only assembles
the argv; process launch lives in the runner. Keeping it pure makes the security
posture unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    """Inputs needed to confine a single installer run."""

    # Absolute path of the installer to execute (read-only bind).
    installer_path: str
    # Absolute working directory the installer may write to (the session cache).
    work_dir: str
    # Absolute Proton/Wine prefix directory (writable, per-session).
    proton_prefix: str
    # Display number for the virtual X server (e.g. ":99").
    display: str
    # Read-only paths the sandbox additionally needs (e.g. the Proton runtime).
    ro_binds: tuple[str, ...] = field(default_factory=tuple)
    # Real, persistent host path bound at the fixed sandbox path /Games -
    # some installers default their own destination to a top-level "Games"
    # folder regardless of which drives are actually available, landing
    # wherever z:\\ (the whole sandboxed filesystem, not backed by anything
    # real for a path that isn't one of this spec's own explicit binds)
    # resolves that to - gone the moment this process exits, same as
    # anything else that lands there. Giving /Games specifically a real
    # backing (a subdirectory of work_dir, so the usual discovery already
    # covers it) is a targeted, single-path workaround for that one
    # convention, not a general fix - see runner.py's own caller.
    games_fallback_dir: str | None = None
    # Extra env vars on top of DISPLAY/WINEPREFIX (e.g. Proton's own
    # STEAM_COMPAT_DATA_PATH/STEAM_COMPAT_CLIENT_INSTALL_PATH - it computes
    # its real wine prefix from the former rather than WINEPREFIX itself).
    extra_env: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def build_bwrap_command(
    spec: SandboxSpec,
    inner_command: list[str],
) -> list[str]:
    """Return the full ``bwrap ... -- <inner_command>`` argv.

    The sandbox is deny-by-default: a fresh mount namespace, no network, a
    private /tmp, a minimal read-only view of the system, and only the specific
    writable paths the installer needs. The library directory and the backend's
    own files are never bound in, so the installer cannot read or corrupt them.
    """
    args: list[str] = [
        "bwrap",
        # Everything --unshare-all covers (user/pid/net/uts/cgroup), except
        # IPC: Wine's X11 driver uses MIT-SHM (XShmPutImage) to blit its
        # windows, which needs a System V shared memory segment the X
        # server - running outside this sandbox, in the container's own IPC
        # namespace - can actually attach to. Unsharing IPC here silently
        # breaks that (the segment id means nothing across namespaces), and
        # Wine doesn't always cleanly fall back to plain XPutImage on
        # failure - observed as the installer window mapping, sizing and
        # focusing correctly, yet its content never actually painting.
        "--unshare-user",
        "--unshare-pid",
        "--unshare-uts",
        "--unshare-cgroup",
        # No network needed: the X11 connection below goes over a unix socket,
        # not loopback TCP (Xvfb runs with -nolisten tcp).
        "--unshare-net",
        "--die-with-parent",
        "--new-session",
        # Minimal read-only system view.
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/bin",
        "/bin",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--ro-bind-try",
        "/etc/fonts",
        "/etc/fonts",
        # Debian's update-alternatives points /usr/bin/wine (and wineboot,
        # winecfg, ...) at a target under here via a symlink outside /usr;
        # without it, execing "wine" resolves the symlink to a dangling path
        # and bwrap fails with "execvp wine: No such file or directory".
        "--ro-bind-try",
        "/etc/alternatives",
        "/etc/alternatives",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        # --dev above gives the sandbox a fresh, minimal /dev (null, zero,
        # tty, ...) with no GPU nodes at all, so Wine/Proton falls back to
        # pure CPU (llvmpipe) rendering for every GL/GLX call regardless of
        # what the container itself can see. Re-bind the host's real render
        # node if there is one; "-try" so this stays a no-op on a host
        # without a GPU rather than failing the whole sandbox.
        "--dev-bind-try",
        "/dev/dri",
        "/dev/dri",
        "--tmpfs",
        "/tmp",
        # The X11 unix-socket directory lives under the host's real /tmp, which
        # the --tmpfs /tmp above hides. Re-bind it (read-only) so the installer
        # can actually reach the Xvfb display; without this DISPLAY is
        # unreachable from inside the sandbox and the installer never starts.
        "--ro-bind",
        "/tmp/.X11-unix",
        "/tmp/.X11-unix",
    ]

    for ro in spec.ro_binds:
        args += ["--ro-bind", ro, ro]

    # The installer file itself is read-only; it cannot rewrite the source ROM.
    args += ["--ro-bind", spec.installer_path, spec.installer_path]

    # Writable, isolated per-session paths.
    args += ["--bind", spec.work_dir, spec.work_dir]
    args += ["--bind", spec.proton_prefix, spec.proton_prefix]
    if spec.games_fallback_dir is not None:
        args += ["--bind", spec.games_fallback_dir, "/Games"]

    # Point Wine/Proton and X clients at the sandboxed prefix and virtual display.
    args += ["--setenv", "DISPLAY", spec.display]
    args += ["--setenv", "WINEPREFIX", spec.proton_prefix]
    for key, value in spec.extra_env:
        args += ["--setenv", key, value]
    args += ["--chdir", spec.work_dir]

    args.append("--")
    args += inner_command
    return args
