// Resolving which file ("disc") the EmulatorJS player should boot.
//
// The player persists the user's disc choice per game in localStorage under
// `player:<romId>:disc`. After a rescan/reimport the rom's files get new
// internal ids, so a saved id can point at a file that no longer exists. Booting
// with that stale id makes the download endpoint 404, which EmulatorJS surfaces
// as a generic "Network Error" (issue #3938). Validate the saved id against the
// rom's current files before using it, and report when it must be forgotten.
//
// Asking the download endpoint for no file in particular instead returns every
// file zipped with a generated .m3u, which EmulatorJS boots with its in-game
// disc switcher (issue #3985). That choice is stored as `ALL_DISCS`.
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

// A set shipping its own .m3u is a curated multi-disc release, so boot it whole;
// anything else boots one file to avoid pulling hundreds of unused MB.
export function defaultDisc(files: readonly DiscFile[]): DiscSelection {
  if (files.length > 1 && files.some(isM3uFile)) return ALL_DISCS;
  return files[0]?.id ?? null;
}

// The file id to download, or null to download the rom whole.
export function bootDiscId(disc: DiscSelection): number | null {
  return typeof disc === "number" ? disc : null;
}

// v1's <Player> owns `player:<romId>:disc` and clears it whenever it is handed
// the null of a whole-set boot, so v2 keeps its own key and reads v1's only as
// a seed for users who have not chosen a disc in v2 yet.
const discKey = (romId: number) => `player:${romId}:disc-selection`;
const v1DiscKey = (romId: number) => `player:${romId}:disc`;

/**
 * The remembered disc if it still matches the rom's files, else the default.
 *
 * A stale entry is dropped instead of being left to 404 the download.
 */
export function resolveRememberedDisc(
  romId: number,
  files: readonly DiscFile[],
): DiscSelection {
  const { disc, stale } = resolveStoredDisc(
    localStorage.getItem(discKey(romId)) ??
      localStorage.getItem(v1DiscKey(romId)),
    files,
  );
  if (stale) localStorage.removeItem(discKey(romId));
  return disc;
}

/** Remember `disc` for the game, or forget it when there is nothing to boot. */
export function rememberDisc(romId: number, disc: DiscSelection): void {
  if (disc === null) localStorage.removeItem(discKey(romId));
  else localStorage.setItem(discKey(romId), disc.toString());
}

function isM3uFile(file: DiscFile): boolean {
  return file.file_name.toLowerCase().endsWith(".m3u");
}
