// Resolving which file ("disc") the EmulatorJS player should boot.
//
// The player persists the user's disc choice per game in localStorage under
// `player:<romId>:disc`. After a rescan/reimport the rom's files get new
// internal ids, so a saved id can point at a file that no longer exists. Booting
// with that stale id makes the download endpoint 404, which EmulatorJS surfaces
// as a generic "Network Error" (issue #3938). Validate the saved id against the
// rom's current files before using it, and report when it must be forgotten.
//
// Asking the download endpoint for the base game's files together returns them
// zipped with a generated .m3u when they carry none, which EmulatorJS boots with
// its in-game disc switcher (issue #3985). That choice is stored as `ALL_DISCS`.
import type { RomFileCategory } from "@/__generated__";
import { userStorage } from "@/composables/useUserLocalStorage";
import { fileExtension } from "@/utils/romFiles";

export const ALL_DISCS = "all";

// A file id to boot on its own, ALL_DISCS to boot every file together, or null
// when the rom has no files to boot at all.
export type DiscSelection = number | typeof ALL_DISCS | null;

interface DiscFile {
  id: number;
  file_name: string;
  category?: RomFileCategory | null;
}

// Media uploaded into a folder rom's subdirectory becomes one of the rom's
// files, so Play would otherwise default to a manual (issue #4074).
const NON_BOOTABLE_CATEGORIES: readonly RomFileCategory[] = [
  "manual",
  "walkthrough",
  "screenshot",
  "soundtrack",
  "patch",
  "cheat",
];

function isBootableFile(file: DiscFile): boolean {
  // A file scanned before categories existed carries none, so absence boots.
  return !file.category || !NON_BOOTABLE_CATEGORIES.includes(file.category);
}

// A file outside any category folder (or in game/) is the base game; one in a
// translations/, hacks/ or similar folder is a variant that boots only when picked.
function isBaseGameFile(file: DiscFile): boolean {
  return !file.category || file.category === "game";
}

// The files ALL_DISCS boots, falling back to every bootable file when the rom
// is nothing but variants.
function allDiscFiles<T extends DiscFile>(files: readonly T[]): readonly T[] {
  const bootable = bootableFiles(files);
  const base = bootable.filter(isBaseGameFile);
  return base.length > 0 ? base : bootable;
}

/** Whether the base game spans several files that can boot together. */
export function offersAllDiscs(files: readonly DiscFile[]): boolean {
  return allDiscFiles(files).length > 1;
}

// Falls back to every file when media is all the rom has, so the player is
// never left with nothing to boot.
export function bootableFiles<T extends DiscFile>(
  files: readonly T[],
): readonly T[] {
  const bootable = files.filter(isBootableFile);
  return bootable.length > 0 ? bootable : files;
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
    return offersAllDiscs(files)
      ? { disc: ALL_DISCS, stale: false }
      : { disc: defaultDisc(files), stale: true };
  }

  const storedDiscId = storedDisc ? parseInt(storedDisc) : null;
  const stored = files.find((f) => f.id === storedDiscId);
  if (stored) {
    // A playlist remembered from before it stopped being offered on its own.
    if (isM3uFile(stored)) return { disc: defaultDisc(files), stale: true };
    return { disc: storedDiscId, stale: false };
  }
  // NaN (non-numeric storage) counts as stored garbage worth forgetting.
  return { disc: defaultDisc(files), stale: storedDiscId !== null };
}

// A playlist only names the discs it sits beside, so booting one on its own
// hands the core a file list of one text file (issue #4306). Booting the set
// whole is what the playlist is for, and that is the ALL_DISCS option.
export function selectableDiscFiles<T extends DiscFile>(
  files: readonly T[],
): readonly T[] {
  const discs = bootableFiles(files).filter((f) => !isM3uFile(f));
  return [
    ...discs.filter(isBaseGameFile),
    ...discs.filter((f) => !isBaseGameFile(f)),
  ];
}

// Sheets that point at sibling track files, so neither the sheet nor a track
// boots alone (issue #4209). Kept in step with backend/utils/m3u.py.
const DESCRIPTOR_EXTENSIONS: readonly string[] = ["cue", "gdi", "ccd", "mds"];

// The raw tracks those sheets point at. Kept in step with backend/utils/m3u.py.
const COMPANION_EXTENSIONS: readonly string[] = [
  "bin",
  "raw",
  "img",
  "sub",
  "mdf",
  "wav",
  "ogg",
  "flac",
  "mp3",
];

function isDescriptorFile(file: DiscFile): boolean {
  return (
    isM3uFile(file) ||
    DESCRIPTOR_EXTENSIONS.includes(fileExtension(file.file_name))
  );
}

// "(Disc 2)", "(CD 2)", "(Disk 1 of 2)", "(Disc 2A)" and "(Disc B)". A letter
// needs a space, so "(CDi)" isn't disc 9. Kept in step with backend/utils/m3u.py.
const DISC_TAG_REGEX =
  /\((?:disc|disk|cd|disque)(?:\s*([0-9]+)[a-z]?|\s+([a-z]))(?:\s+of\s+[0-9]+)?\)/i;

/** The disc number a file's name claims (A counts as 1), or null. */
export function discNumber(fileName: string): number | null {
  const match = DISC_TAG_REGEX.exec(fileName);
  if (!match) return null;
  const [, number, letter] = match;
  if (number) return parseInt(number);
  return letter!.toLowerCase().charCodeAt(0) - "a".charCodeAt(0) + 1;
}

// Numbered discs first and in order, then the rest by name, as the backend sorts.
function compareDiscs(a: DiscFile, b: DiscFile): number {
  const na = discNumber(a.file_name);
  const nb = discNumber(b.file_name);
  if ((na === null) !== (nb === null)) return na === null ? 1 : -1;
  if (na !== nb) return na! - nb!;
  if (a.file_name === b.file_name) return 0;
  return a.file_name < b.file_name ? -1 : 1;
}

/** The discs a stream can start on, picked and ordered like the backend's
 *  `disc_files`: media and patches are left out, and a sheet replaces its tracks. */
export function streamDiscFiles<T extends DiscFile>(
  files: readonly T[],
  patchExtensions: readonly string[],
): readonly T[] {
  let discs = files.filter(
    (f) =>
      isBootableFile(f) &&
      !isM3uFile(f) &&
      !patchExtensions.includes(`.${fileExtension(f.file_name)}`),
  );
  if (discs.some(isDescriptorFile)) {
    discs = discs.filter(
      (f) => !COMPANION_EXTENSIONS.includes(fileExtension(f.file_name)),
    );
  }
  return discs.sort(compareDiscs);
}

// The backend's `playlist_set`: the base game's files, or every file when the
// base has no disc.
function streamPlaylistSet<T extends DiscFile>(
  files: readonly T[],
  patchExtensions: readonly string[],
): readonly T[] {
  const base = files.filter(isBaseGameFile);
  return streamDiscFiles(base, patchExtensions).length > 0 ? base : files;
}

/** The discs a running stream can swap to, as the backend's `playlist_files` picks them. */
export function streamSwapDiscFiles<T extends DiscFile>(
  files: readonly T[],
  patchExtensions: readonly string[],
): readonly T[] {
  return streamDiscFiles(
    streamPlaylistSet(files, patchExtensions),
    patchExtensions,
  );
}

/** Whether the stream's playlist set ships its own .m3u, as `Rom.has_m3u_file` checks. */
export function streamHasPlaylist(
  files: readonly DiscFile[],
  patchExtensions: readonly string[],
): boolean {
  return streamPlaylistSet(files, patchExtensions).some(isM3uFile);
}

// A set carrying a playlist or disc sheet only boots whole; anything else boots
// one file to avoid pulling hundreds of unused MB.
export function defaultDisc(files: readonly DiscFile[]): DiscSelection {
  const base = allDiscFiles(files);
  if (base.length > 1 && base.some(isDescriptorFile)) return ALL_DISCS;
  return base[0]?.id ?? null;
}

// The file id to download, or null to download the rom whole.
export function bootDiscId(disc: DiscSelection): number | null {
  return typeof disc === "number" ? disc : null;
}

/** The file ids to download, or none for the rom whole; ALL_DISCS is the base set alone. */
export function bootFileIds(
  disc: DiscSelection,
  files: readonly DiscFile[],
): number[] {
  const id = bootDiscId(disc);
  if (id !== null) return [id];
  if (disc !== ALL_DISCS) return [];
  const set = allDiscFiles(files);
  return set.length < files.length ? set.map((f) => f.id) : [];
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
    userStorage.getItem(discKey(romId)) ??
      userStorage.getItem(v1DiscKey(romId)),
    files,
  );
  if (stale) userStorage.removeItem(discKey(romId));
  return disc;
}

/** Remember `disc` for the game, or forget it when there is nothing to boot. */
export function rememberDisc(romId: number, disc: DiscSelection): void {
  if (disc === null) userStorage.removeItem(discKey(romId));
  else userStorage.setItem(discKey(romId), disc.toString());
}

function isM3uFile(file: DiscFile): boolean {
  return file.file_name.toLowerCase().endsWith(".m3u");
}
