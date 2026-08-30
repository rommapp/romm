// The Jukebox's browse modes, shared so that surfaces which react to them
// (the mini player, which hides while a full player is on screen) can't
// drift from the view that defines them.
export const JUKEBOX_MODES = [
  "album",
  "artist",
  "decade",
  "favorite",
  "genre",
  "platform",
  "recent",
  "play-all",
  "station",
] as const;

export type JukeboxPlayerMode = (typeof JUKEBOX_MODES)[number];
export type JukeboxMode = JukeboxPlayerMode | "home";

const MODES = new Set<string>(JUKEBOX_MODES);

/** `home` is the fallback: it is the mode with no `?mode=` param. */
export function modeFromQuery(value: unknown): JukeboxMode {
  return typeof value === "string" && MODES.has(value)
    ? (value as JukeboxPlayerMode)
    : "home";
}

export function isJukeboxPlayerMode(
  value: unknown,
): value is JukeboxPlayerMode {
  return typeof value === "string" && MODES.has(value);
}
