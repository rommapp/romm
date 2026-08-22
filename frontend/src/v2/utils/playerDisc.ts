// Resolving which file ("disc") the EmulatorJS player should boot.
//
// The player persists the user's disc choice per game in localStorage under
// `player:<romId>:disc`. After a rescan/reimport the rom's files get new
// internal ids, so a saved id can point at a file that no longer exists. Booting
// with that stale id makes the download endpoint 404, which EmulatorJS surfaces
// as a generic "Network Error" (issue #3938). Validate the saved id against the
// rom's current files before using it, and report when it must be forgotten.
//
// A multi-file rom can also be booted whole (issue #3985): asking the download
// endpoint for no file in particular returns every file zipped together with a
// generated .m3u playlist, which EmulatorJS boots with its in-game disc
// switcher. That choice is stored as `ALL_DISCS`.
export const ALL_DISCS = "all";

// A file id to boot on its own, ALL_DISCS to boot every file together, or null
// when the rom has no files to boot at all.
export type DiscSelection = number | typeof ALL_DISCS | null;

interface DiscFile {
  id: number;
  file_name: string;
}

export interface ResolvedDisc {
  disc: DiscSelection;
  // True when a value was stored but no longer matches the rom's files, so the
  // caller should drop the stale localStorage entry.
  stale: boolean;
}

export function resolveStoredDisc(
  storedDisc: string | null,
  files: readonly DiscFile[],
): ResolvedDisc {
  if (storedDisc === ALL_DISCS) {
    // Nothing left to boot together once the rom is down to a single file.
    return files.length > 1
      ? { disc: ALL_DISCS, stale: false }
      : { disc: defaultDisc(files), stale: true };
  }

  const storedDiscId = storedDisc ? parseInt(storedDisc) : null;
  if (storedDiscId !== null && files.some((f) => f.id === storedDiscId)) {
    return { disc: storedDiscId, stale: false };
  }
  // NaN (non-numeric storage) counts as stored garbage worth forgetting.
  return { disc: defaultDisc(files), stale: storedDiscId !== null };
}

// Sets that ship their own .m3u are curated multi-disc releases, so boot them
// whole and let the user swap discs from the emulator menu. Every other set
// keeps booting a single file: pulling the whole set can mean hundreds of extra
// MB over the wire, and EmulatorJS only prefers the playlist over a bare .chd /
// .iso for cue-based sets anyway.
export function defaultDisc(files: readonly DiscFile[]): DiscSelection {
  if (files.length > 1 && files.some(isM3uFile)) return ALL_DISCS;
  return files[0]?.id ?? null;
}

// The file id to download, or null to download the rom whole.
export function bootDiscId(disc: DiscSelection): number | null {
  return typeof disc === "number" ? disc : null;
}

function isM3uFile(file: DiscFile): boolean {
  return file.file_name.toLowerCase().endsWith(".m3u");
}
