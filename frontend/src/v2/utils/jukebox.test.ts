import { describe, expect, it } from "vitest";
import {
  isJukeboxPlayerMode,
  JUKEBOX_MODES,
  parseJukeboxMode,
} from "./jukebox";

describe("parseJukeboxMode", () => {
  it("accepts every published mode", () => {
    for (const mode of JUKEBOX_MODES) {
      expect(parseJukeboxMode(mode)).toBe(mode);
    }
  });

  it("falls back to home for anything else", () => {
    for (const value of [undefined, null, "", "nope", 3, ["album"]]) {
      expect(parseJukeboxMode(value)).toBe("home");
    }
  });
});

describe("isJukeboxPlayerMode", () => {
  it("is true only for modes that host a full player", () => {
    expect(isJukeboxPlayerMode("station")).toBe(true);
    expect(isJukeboxPlayerMode("album")).toBe(true);
    // "home" shows launch tiles, not a player, so the mini player stays up.
    expect(isJukeboxPlayerMode("home")).toBe(false);
    expect(isJukeboxPlayerMode(undefined)).toBe(false);
  });
});
