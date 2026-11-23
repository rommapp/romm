// The Jukebox's browse modes, shared with the surfaces that react to them
// (the mini player hides while a full player is on screen).
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

/** Size of the fixed "recently added" queue. */
export const RECENTLY_ADDED_LIMIT = 25;

/** Locale key for each mode's display name, shared by the launch tiles and
 *  the page header so a subgroup is called the same thing everywhere. */
export const JUKEBOX_MODE_LABEL_KEYS: Record<JukeboxPlayerMode, string> = {
  station: "common.free-radio",
  decade: "common.decade-mix",
  recent: "common.recently-added-soundtracks",
  favorite: "common.favorite-soundtracks",
  "play-all": "common.play-all",
  album: "common.music-by-album",
  platform: "common.soundtracks-by-platform",
  artist: "common.music-by-artist",
  genre: "common.soundtracks-by-genre",
};

const MODES = new Set<string>(JUKEBOX_MODES);

/** `home` is the fallback: it is the mode with no path segment. */
export function parseJukeboxMode(value: unknown): JukeboxMode {
  return typeof value === "string" && MODES.has(value)
    ? (value as JukeboxPlayerMode)
    : "home";
}

export function isJukeboxPlayerMode(
  value: unknown,
): value is JukeboxPlayerMode {
  return typeof value === "string" && MODES.has(value);
}
