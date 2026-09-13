// Validation for the two pieces of launch input that come from the renderer.
// Deliberately free of Electron imports so it can be unit tested directly.

import { LaunchError, type LaunchRequest } from "../shared/types.ts";

/** Resolve the renderer's download path against the bound server. Anything that
 *  lands off-origin or outside /api/ is rejected rather than normalised. */
export function resolveDownloadUrl(
  serverUrl: string,
  downloadPath: string,
): URL {
  if (!downloadPath.startsWith("/") || downloadPath.startsWith("//")) {
    throw new LaunchError(
      "invalid-request",
      `Download path must be server-relative: ${downloadPath}`,
    );
  }

  const base = new URL(serverUrl);
  const resolved = new URL(downloadPath, base);
  if (resolved.origin !== base.origin) {
    throw new LaunchError(
      "invalid-request",
      `Download path resolves off-origin: ${resolved.origin}`,
    );
  }
  if (!resolved.pathname.startsWith("/api/")) {
    throw new LaunchError(
      "invalid-request",
      `Download path is not an API route: ${resolved.pathname}`,
    );
  }
  return resolved;
}

/** Characters that are unsafe in a filename on at least one supported OS. */
const UNSAFE_FILENAME_CHARS = new RegExp('[/\\\\:*?"<>|]', "g");

/** Reduce a server-supplied name to one safe filename component; the result is
 *  only ever joined onto the cache directory. */
export function safeCacheFileName(fileName: string, romId: number): string {
  const cleaned = fileName
    .replace(UNSAFE_FILENAME_CHARS, "_")
    .replace(/^\.+/, "")
    .trim()
    .slice(0, 120);
  // Prefixing with the ROM id keeps two games that share a filename apart and
  // guarantees a non-empty name when cleaning removes everything.
  return `${romId}-${cleaned || "rom"}`;
}

/** Check a launch request's shape before any of it reaches the filesystem or a
 *  child process. */
export function validateLaunchRequest(value: unknown): LaunchRequest {
  if (typeof value !== "object" || value === null) {
    throw new LaunchError(
      "invalid-request",
      "Launch request must be an object.",
    );
  }
  const candidate = value as Record<string, unknown>;

  const romId = candidate.romId;
  if (typeof romId !== "number" || !Number.isInteger(romId) || romId <= 0) {
    throw new LaunchError(
      "invalid-request",
      "romId must be a positive integer.",
    );
  }

  const downloadPath = candidate.downloadPath;
  if (typeof downloadPath !== "string" || downloadPath.length === 0) {
    throw new LaunchError("invalid-request", "downloadPath is required.");
  }

  const fileName = candidate.fileName;
  if (typeof fileName !== "string" || fileName.length === 0) {
    throw new LaunchError("invalid-request", "fileName is required.");
  }

  const platformSlug = candidate.platformSlug;
  if (typeof platformSlug !== "string" || platformSlug.length === 0) {
    throw new LaunchError("invalid-request", "platformSlug is required.");
  }

  const cores = candidate.cores;
  if (!Array.isArray(cores) || cores.some((core) => typeof core !== "string")) {
    throw new LaunchError(
      "invalid-request",
      "cores must be an array of strings.",
    );
  }

  const name = candidate.name;
  if (name !== undefined && typeof name !== "string") {
    throw new LaunchError("invalid-request", "name must be a string.");
  }

  return {
    romId,
    downloadPath,
    fileName,
    platformSlug,
    cores: cores as string[],
    ...(name === undefined ? {} : { name }),
  };
}
