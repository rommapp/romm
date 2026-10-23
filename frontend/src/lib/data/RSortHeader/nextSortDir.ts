import type { RSortDir } from "./types";

/** Re-picking the active column flips it; any other column starts ascending. */
export function nextSortDir(active: boolean, dir: RSortDir): RSortDir {
  return active && dir === "asc" ? "desc" : "asc";
}
