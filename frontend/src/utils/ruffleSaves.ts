// Ruffle keeps each SharedObject in localStorage as a base64 `.sol` file, keyed
// `<host>/<SWF path or an ancestor>/<name>`, a `/` in a name prefixed with `#`.
// Ruffle picks those keys itself, so they cannot be scoped to the user.
/* eslint-disable romm/no-unscoped-local-storage */
import { unzipSync, zipSync } from "fflate";

/** A game's SharedObjects, keyed by their storage key without the host. */
export type RuffleSaves = Record<string, Uint8Array>;
/** The same SharedObjects as stored, still base64, for a cheap comparison. */
export type RuffleStorage = Record<string, string>;

const SOL_MAGIC = [0x00, 0xbf];
const SOL_SIGNATURE = "TCSO";
const SOL_SIGNATURE_OFFSET = 6;

function fromBase64(value: string): Uint8Array | null {
  try {
    return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
  } catch {
    return null;
  }
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}

function isSolFile(bytes: Uint8Array): boolean {
  if (bytes[0] !== SOL_MAGIC[0] || bytes[1] !== SOL_MAGIC[1]) return false;
  const signature = String.fromCharCode(
    ...bytes.subarray(
      SOL_SIGNATURE_OFFSET,
      SOL_SIGNATURE_OFFSET + SOL_SIGNATURE.length,
    ),
  );
  return signature === SOL_SIGNATURE;
}

/** The path Ruffle files a SWF's SharedObjects under, as it derives it. */
export function swfStoragePath(swfUrl: string): string {
  return new URL(swfUrl, document.baseURI).pathname.replace(/^\/+|\/+$/g, "");
}

// The SWF's own path and every ancestor, down to the root's empty segment.
function storageScopes(swfPath: string): string[] {
  const segments = swfPath.split("/").filter(Boolean);
  return segments
    .map((_, index, all) => all.slice(0, all.length - index).join("/"))
    .concat("");
}

function ownsKey(entry: string, scopes: string[]): boolean {
  return scopes.some((scope) => {
    if (!entry.startsWith(`${scope}/`)) return false;
    const name = entry.slice(scope.length + 1);
    // A deeper path belongs to another SWF; only `#` names may hold a slash.
    return name.length > 0 && (!name.includes("/") || name.startsWith("#"));
  });
}

function storageKeys(): string[] {
  try {
    return Array.from({ length: localStorage.length }, (_, index) =>
      localStorage.key(index),
    ).filter((key): key is string => key !== null);
  } catch {
    return [];
  }
}

/** The stored entries a SWF can reach on this host, undecoded. */
export function readRuffleStorage(
  host: string,
  swfPath: string,
): RuffleStorage {
  const prefix = `${host}/`;
  const scopes = storageScopes(swfPath);
  const stored: RuffleStorage = {};
  for (const key of storageKeys()) {
    if (!key.startsWith(prefix)) continue;
    const entry = key.slice(prefix.length);
    if (ownsKey(entry, scopes)) stored[entry] = localStorage.getItem(key) ?? "";
  }
  return stored;
}

/** The SharedObjects among stored entries, skipping any that are not one. */
export function decodeRuffleStorage(stored: RuffleStorage): RuffleSaves {
  const saves: RuffleSaves = {};
  for (const [entry, value] of Object.entries(stored)) {
    const bytes = fromBase64(value);
    if (bytes && isSolFile(bytes)) saves[entry] = bytes;
  }
  return saves;
}

/** The SharedObjects a SWF can reach on this host. */
export function readRuffleSaves(host: string, swfPath: string): RuffleSaves {
  return decodeRuffleStorage(readRuffleStorage(host, swfPath));
}

export function writeRuffleSaves(host: string, saves: RuffleSaves): void {
  for (const [entry, bytes] of Object.entries(saves)) {
    localStorage.setItem(`${host}/${entry}`, toBase64(bytes));
  }
}

export function removeRuffleSaves(host: string, entries: string[]): void {
  for (const entry of entries) localStorage.removeItem(`${host}/${entry}`);
}

/** Whether two reads of storage hold the same entries. */
export function sameRuffleStorage(a: RuffleStorage, b: RuffleStorage): boolean {
  const entries = Object.keys(a);
  return (
    entries.length === Object.keys(b).length &&
    entries.every((entry) => a[entry] === b[entry])
  );
}

export function zipRuffleSaves(saves: RuffleSaves): Uint8Array {
  return zipSync(saves);
}

/** The SharedObjects in an archive that the SWF at `swfPath` can reach. */
export function unzipRuffleSaves(
  bytes: Uint8Array,
  swfPath: string,
): RuffleSaves {
  const scopes = storageScopes(swfPath);
  const saves: RuffleSaves = {};
  for (const [entry, content] of Object.entries(unzipSync(bytes))) {
    if (ownsKey(entry, scopes) && isSolFile(content)) saves[entry] = content;
  }
  return saves;
}
