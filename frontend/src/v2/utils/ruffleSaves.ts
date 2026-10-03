// Ruffle keeps each Flash SharedObject in localStorage as a base64 `.sol` file,
// keyed `<host>/<local path>/<name>`. The local path is the SWF's URL path or
// one of its ancestors, and a name holding `/` is prefixed with `#`.
import { unzipSync, zipSync } from "fflate";

/** A game's SharedObjects, keyed by their storage key without the host. */
export type RuffleSaves = Record<string, Uint8Array>;

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

/** The SharedObjects a SWF can reach on this host. */
export function readRuffleSaves(host: string, swfPath: string): RuffleSaves {
  const prefix = `${host}/`;
  const scopes = storageScopes(swfPath);
  const saves: RuffleSaves = {};
  for (const key of storageKeys()) {
    if (!key.startsWith(prefix)) continue;
    const entry = key.slice(prefix.length);
    if (!ownsKey(entry, scopes)) continue;
    const bytes = fromBase64(localStorage.getItem(key) ?? "");
    if (bytes && isSolFile(bytes)) saves[entry] = bytes;
  }
  return saves;
}

export function writeRuffleSaves(host: string, saves: RuffleSaves): void {
  for (const [entry, bytes] of Object.entries(saves)) {
    localStorage.setItem(`${host}/${entry}`, toBase64(bytes));
  }
}

export function removeRuffleSaves(host: string, entries: string[]): void {
  for (const entry of entries) localStorage.removeItem(`${host}/${entry}`);
}

export function zipRuffleSaves(saves: RuffleSaves): Uint8Array {
  return zipSync(saves);
}

export function unzipRuffleSaves(bytes: Uint8Array): RuffleSaves {
  const saves: RuffleSaves = {};
  for (const [entry, content] of Object.entries(unzipSync(bytes))) {
    if (!entry.endsWith("/") && isSolFile(content)) saves[entry] = content;
  }
  return saves;
}
