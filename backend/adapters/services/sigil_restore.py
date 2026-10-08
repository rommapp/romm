"""Restore a stored save unit as the files an emulator reads, through sigil."""

import asyncio
import io
import os
import tempfile
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal

from adapters.services.sigil import SigilGame, sigil_binding

# Saves on these carry no game id, so a merge claims the unit's save names.
VOLUME_PLATFORMS: Final = frozenset({"saturn", "segacd", "dreamcast"})

_UNMANAGED: Final = "unmanaged"


class RefusalCode(StrEnum):
    """Why sigil refused a restore, by its error code's name."""

    CONFLICT = "CONFLICT"
    UNCOLLECTED = "UNCOLLECTED"
    EXISTS = "EXISTS"
    DAMAGED = "DAMAGED"
    REGION = "REGION"
    NO_SPACE = "NO_SPACE"
    NOT_FOUND = "NOT_FOUND"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    NO_TARGET = "NO_TARGET"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID_ARG = "INVALID_ARG"
    IO = "IO"
    OTHER = "OTHER"


_REFUSAL_CLASSES: Final[Mapping[str, RefusalCode]] = {
    "SigilConflictError": RefusalCode.CONFLICT,
    "SigilUncollectedError": RefusalCode.UNCOLLECTED,
    "SigilExistsError": RefusalCode.EXISTS,
    "SigilDamagedError": RefusalCode.DAMAGED,
    "SigilRegionError": RefusalCode.REGION,
    "SigilNoSpaceError": RefusalCode.NO_SPACE,
    "SigilNotFoundError": RefusalCode.NOT_FOUND,
    "SigilUnsupportedFormatError": RefusalCode.UNSUPPORTED_FORMAT,
    "SigilNoTargetError": RefusalCode.NO_TARGET,
    "SigilAmbiguousError": RefusalCode.AMBIGUOUS,
    "SigilInvalidArgError": RefusalCode.INVALID_ARG,
    "SigilIOError": RefusalCode.IO,
}


@dataclass(frozen=True)
class RestoreTarget:
    """The emulator a restore writes for.

    Attributes:
        core: sigil's layout id, a libretro core name or an emulator id.
        content_path: the ROM file name the emulator loads; `{stem}` comes from it.
    """

    core: str
    options: Mapping[str, str]
    profile: str | None
    content_path: str


@dataclass(frozen=True)
class RestoreCompanion:
    """A game whose saves the restored game reads, with its stored unit."""

    game_ids: tuple[str, ...]
    unit: bytes


@dataclass(frozen=True)
class RestoreProfile:
    id: str
    name: str


@dataclass(frozen=True)
class RestoredSave:
    """The files a restore produced, by path relative to the emulator's save root."""

    files: Mapping[str, bytes]


class SaveRestoreError(Exception):
    """A restore that produced nothing to serve."""


class SigilRefusal(SaveRestoreError):
    """Sigil refused the restore and wrote nothing."""

    def __init__(
        self,
        code: RefusalCode,
        message: str,
        problem: str = "",
        profiles: tuple[RestoreProfile, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.problem = problem
        self.profiles = profiles


class SharedContainerRequired(SaveRestoreError):
    """The target is a card or volume every game shares, so the client must send its own."""

    def __init__(self, container_path: str) -> None:
        super().__init__(
            f"{container_path} is shared by every game: send it to merge this "
            "game's saves into it"
        )
        self.container_path = container_path


class ContainerMismatch(SaveRestoreError):
    """The restore wrote somewhere other than the container the client sent."""

    def __init__(
        self,
        container_path: str,
        written: tuple[str, ...],
        options: Mapping[str, str | None],
    ) -> None:
        hint = ", ".join(
            f"{key}={value}" if value is not None else key
            for key, value in options.items()
        )
        super().__init__(
            f"The restore wrote {', '.join(written)}, not {container_path}"
            + (f"; the option that selects the file is {hint}" if hint else "")
        )
        self.container_path = container_path
        self.written = written
        self.options = dict(options)


def _binding() -> Any:
    binding = sigil_binding()
    if binding is None:
        raise SaveRestoreError("sigil isn't installed")
    return binding


def _refusal(exc: Exception, companions: Sequence[RestoreCompanion]) -> SigilRefusal:
    code = _REFUSAL_CLASSES.get(type(exc).__name__, RefusalCode.OTHER)
    message = str(exc)
    if code is RefusalCode.INVALID_ARG and companions:
        message = (
            "companions only go on cards and volumes: layouts with profiles and "
            "cartridges (N64, GB, GBC) take none"
        )
    profiles = tuple(
        RestoreProfile(id=p.id, name=p.name) for p in getattr(exc, "profiles", ())
    )
    return SigilRefusal(code, message, getattr(exc, "problem", ""), profiles)


def _files_under(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    )


def _sync_kwargs(game: SigilGame, target: RestoreTarget, root: Path) -> dict[str, Any]:
    return {
        "game": game.result,
        "core": target.core,
        "content_path": target.content_path,
        "save_root": root,
        "options": dict(target.options),
        "game_ids": game.game_ids,
        "profile": target.profile,
    }


def _restore(
    unit: bytes,
    game: SigilGame,
    target: RestoreTarget,
    root: Path,
    companions: Sequence[RestoreCompanion],
    *,
    mode: Literal["managed", "unmanaged"] = "managed",
    state: bytes | None = None,
    overwrite_local: bool = False,
) -> None:
    binding = _binding()
    try:
        binding.restore(
            unit,
            **_sync_kwargs(game, target, root),
            companions=[
                binding.SigilCompanion(game_ids=c.game_ids, unit=c.unit)
                for c in companions
            ],
            mode=mode,
            state=state,
            overwrite_local=overwrite_local,
        )
    except binding.SigilError as exc:
        raise _refusal(exc, companions) from exc


def _restore_per_game(
    unit: bytes,
    game: SigilGame,
    target: RestoreTarget,
    companions: Sequence[RestoreCompanion],
) -> RestoredSave:
    binding = _binding()
    with tempfile.TemporaryDirectory(prefix="romm-restore-") as tmp:
        root = Path(tmp)
        _restore(unit, game, target, root, companions)
        written = _files_under(root)
        if not written:
            raise SigilRefusal(RefusalCode.NOT_FOUND, "The restore wrote no files")
        try:
            located = binding.locate_saves(
                game.result,
                target.core,
                target.content_path,
                save_root=root,
                options=dict(target.options),
                profile=target.profile,
            )
        except binding.SigilError as exc:
            raise _refusal(exc, companions) from exc
        # `unkeyed` holds the shared files under the root: what restore wrote
        # there is a card or volume every game keeps its saves on.
        shared = sorted(set(written) & set(located.unkeyed))
        if shared:
            raise SharedContainerRequired(shared[0])
        return RestoredSave({path: (root / path).read_bytes() for path in written})


def _unit_save_names(unit: bytes, scratch: Path) -> list[str]:
    """The save names on each volume a unit holds, which a merge claims for its game."""
    binding = _binding()
    volumes: Iterable[bytes]
    if zipfile.is_zipfile(io.BytesIO(unit)):
        with zipfile.ZipFile(io.BytesIO(unit)) as zf:
            volumes = [zf.read(info) for info in zf.infolist() if not info.is_dir()]
    else:
        volumes = [unit]
    names: list[str] = []
    for index, volume in enumerate(volumes):
        path = scratch / f"volume-{index}"
        path.write_bytes(volume)
        try:
            listing = binding.list_card(path)
        except binding.SigilError:
            continue
        names.extend(entry.name for entry in listing.entries)
    return names


def restore_layouts(platform: str) -> tuple[Any, ...]:
    """Sigil's layout rows for a sigil platform slug, the libretro default first.

    Raises:
        SaveRestoreError: the binding is absent.
    """
    return tuple(_binding().layouts(platform))


def _region_option(platform: str, core: str) -> str:
    """The option `core`'s layout picks a shared file by the disc's region, or ""."""
    try:
        rows = restore_layouts(platform)
    except _binding().SigilError:
        return ""
    return next((row.region_option for row in rows if row.id == core), "")


def _selecting_options(
    alternates: Iterable[Any], container_path: str, platform: str, core: str
) -> dict[str, str | None]:
    """The options that make the layout take the sent container, where known."""
    options: dict[str, str | None] = {}
    for alternate in alternates:
        if alternate.path == container_path:
            options.update(alternate.options)
    region = _region_option(platform, core)
    if region and region not in options:
        options[region] = None
    return options


def _merge_into_container(
    unit: bytes,
    game: SigilGame,
    target: RestoreTarget,
    companions: Sequence[RestoreCompanion],
    container_path: str,
    container: bytes,
) -> RestoredSave:
    binding = _binding()
    with tempfile.TemporaryDirectory(prefix="romm-restore-") as tmp:
        root = Path(tmp, "root")
        scratch = Path(tmp, "scratch")
        scratch.mkdir()
        sent = root / container_path
        if not sent.resolve().is_relative_to(root.resolve()):
            raise SaveRestoreError(f"{container_path} leaves the save root")
        sent.parent.mkdir(parents=True, exist_ok=True)
        sent.write_bytes(container)
        # Sigil writes only a file whose bytes change, and writing sets the mtime.
        os.utime(sent, ns=(0, 0))

        try:
            located = binding.locate_saves(
                game.result,
                target.core,
                target.content_path,
                save_root=root,
                options=dict(target.options),
                profile=target.profile,
            )
            if game.result.platform in VOLUME_PLATFORMS:
                # A managed merge would drop every other game's saves on the volume.
                seen = binding.collect(
                    **_sync_kwargs(game, target, root),
                    mode=_UNMANAGED,
                    claimed=_unit_save_names(unit, scratch),
                    companions=[
                        binding.SigilCompanion(game_ids=c.game_ids) for c in companions
                    ],
                )
                _restore(
                    unit,
                    game,
                    target,
                    root,
                    companions,
                    mode=_UNMANAGED,
                    state=seen.state,
                    overwrite_local=True,
                )
            else:
                _restore(unit, game, target, root, companions, overwrite_local=True)
        except binding.SigilError as exc:
            raise _refusal(exc, companions) from exc

        written = tuple(
            path
            for path in _files_under(root)
            if path != container_path or (root / path).stat().st_mtime_ns != 0
        )
        moved = tuple(path for path in written if path != container_path)
        if moved or not sent.is_file():
            raise ContainerMismatch(
                container_path,
                moved,
                _selecting_options(
                    located.alternates,
                    container_path,
                    game.result.platform,
                    target.core,
                ),
            )
        return RestoredSave({container_path: sent.read_bytes()})


async def restore_per_game(
    unit: bytes,
    game: SigilGame,
    target: RestoreTarget,
    companions: Sequence[RestoreCompanion] = (),
) -> RestoredSave:
    """Restore a unit into an empty save root and return what lands there.

    Raises:
        SharedContainerRequired: the target is a card or volume every game shares.
        SigilRefusal: sigil refused the restore.
    """
    return await asyncio.to_thread(_restore_per_game, unit, game, target, companions)


async def merge_into_container(
    unit: bytes,
    game: SigilGame,
    target: RestoreTarget,
    container_path: str,
    container: bytes,
    companions: Sequence[RestoreCompanion] = (),
) -> RestoredSave:
    """Merge a unit into the client's own card or volume and return it rewritten.

    Args:
        container_path: where the container sits under the save root; the caller
            has checked it stays inside.

    Raises:
        ContainerMismatch: the restore wrote anywhere but `container_path`.
        SigilRefusal: sigil refused the merge.
    """
    return await asyncio.to_thread(
        _merge_into_container,
        unit,
        game,
        target,
        companions,
        container_path,
        container,
    )
