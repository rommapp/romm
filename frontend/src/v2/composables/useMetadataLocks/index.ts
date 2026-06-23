// useMetadataLocks: shared lock-state helpers for the edit-ROM dialog.
//
// A locked metadata field is frozen permanently: the backend refuses to let
// manual edits or rescans change it (see the rom's `metadata_locks`). The
// edit sections store the set of locked keys on `rom.metadata_locks`; this
// composable reads/toggles that list and re-emits the updated rom so the
// parent dialog stays the single owner of the in-flight edit.
import type { UpdateRom } from "@/services/api/rom";

export function useMetadataLocks(
  getRom: () => UpdateRom,
  onUpdate: (rom: UpdateRom) => void,
) {
  function isLocked(key: string): boolean {
    return (getRom().metadata_locks ?? []).includes(key);
  }

  function toggleLock(key: string): void {
    const rom = getRom();
    const current = rom.metadata_locks ?? [];
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    onUpdate({ ...rom, metadata_locks: next });
  }

  return { isLocked, toggleLock };
}
