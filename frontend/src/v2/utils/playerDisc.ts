// Resolving which file ("disc") the EmulatorJS player should boot.
//
// The player persists the user's disc choice per game in localStorage under
// `player:<romId>:disc`. After a rescan/reimport the rom's files get new
// internal ids, so a saved id can point at a file that no longer exists. Booting
// with that stale id makes the download endpoint 404, which EmulatorJS surfaces
// as a generic "Network Error" (issue #3938). Validate the saved id against the
// rom's current files before using it, and report when it must be forgotten.
export interface ResolvedDisc {
  // The file id to boot, or null when the rom has no files.
  discId: number | null;
  // True when a value was stored but no longer matches a current file, so the
  // caller should drop the stale localStorage entry.
  stale: boolean;
}

export function resolveStoredDisc(
  storedDisc: string | null,
  files: readonly { id: number }[],
): ResolvedDisc {
  const storedDiscId = storedDisc ? parseInt(storedDisc) : null;
  if (storedDiscId !== null && files.some((f) => f.id === storedDiscId)) {
    return { discId: storedDiscId, stale: false };
  }
  // NaN (non-numeric storage) counts as stored garbage worth forgetting.
  return { discId: files[0]?.id ?? null, stale: storedDiscId !== null };
}
