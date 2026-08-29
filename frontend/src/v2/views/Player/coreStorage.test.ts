import { beforeEach, describe, expect, it } from "vitest";
import { rememberCore, resolveRememberedCore } from "./coreStorage";

const ARCADE_CORES = ["mame2003", "mame2003_plus", "fbneo"];
const ROM_ID = 7;
const SLUG = "arcade";

describe("coreStorage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("falls back to the platform's first core when nothing is remembered", () => {
    expect(resolveRememberedCore(ROM_ID, SLUG, ARCADE_CORES)).toBe("mame2003");
  });

  it("remembers a launch under both the game and the platform", () => {
    rememberCore(ROM_ID, SLUG, "mame2003_plus");

    expect(localStorage.getItem(`player:${ROM_ID}:core`)).toBe("mame2003_plus");
    expect(localStorage.getItem(`player:${SLUG}:core`)).toBe("mame2003_plus");
  });

  it("applies the platform default to a game never launched before", () => {
    rememberCore(ROM_ID, SLUG, "mame2003_plus");

    expect(resolveRememberedCore(999, SLUG, ARCADE_CORES)).toBe(
      "mame2003_plus",
    );
  });

  it("prefers the game's own core over the platform default", () => {
    rememberCore(ROM_ID, SLUG, "mame2003_plus");
    localStorage.setItem(`player:${ROM_ID}:core`, "fbneo");

    expect(resolveRememberedCore(ROM_ID, SLUG, ARCADE_CORES)).toBe("fbneo");
  });

  it("skips a remembered core the platform no longer supports", () => {
    localStorage.setItem(`player:${ROM_ID}:core`, "mame2010");
    localStorage.setItem(`player:${SLUG}:core`, "fbneo");

    expect(resolveRememberedCore(ROM_ID, SLUG, ARCADE_CORES)).toBe("fbneo");
  });

  it("falls back to the first core when every remembered one is stale", () => {
    localStorage.setItem(`player:${ROM_ID}:core`, "mame2010");
    localStorage.setItem(`player:${SLUG}:core`, "mame2016");

    expect(resolveRememberedCore(ROM_ID, SLUG, ARCADE_CORES)).toBe("mame2003");
  });

  it("forgets both keys when the selection is cleared", () => {
    rememberCore(ROM_ID, SLUG, "mame2003_plus");
    rememberCore(ROM_ID, SLUG, null);

    expect(localStorage.getItem(`player:${ROM_ID}:core`)).toBeNull();
    expect(localStorage.getItem(`player:${SLUG}:core`)).toBeNull();
  });
});
