import { describe, expect, it } from "vitest";
import {
  resolveBezelHost,
  resolveBezelUrl,
  resolveStoredBezelVisible,
} from "./playerBezel";

// Mirrors FRONTEND_RESOURCES_PATH; asserted literally like the box-faces test.
const RES = "/assets/romm/resources";

describe("resolveBezelUrl", () => {
  it("prefixes a relative bezel path with the resources base", () => {
    expect(resolveBezelUrl("roms/279/158934/bezel/bezel.png")).toBe(
      `${RES}/roms/279/158934/bezel/bezel.png`,
    );
  });

  it("returns null when no bezel path is set", () => {
    expect(resolveBezelUrl(null)).toBeNull();
    expect(resolveBezelUrl(undefined)).toBeNull();
  });

  it("returns null for an empty path rather than a bare resources root", () => {
    expect(resolveBezelUrl("")).toBeNull();
  });
});

describe("resolveBezelHost", () => {
  it("adopts the fullscreen element when it is the #game container", () => {
    const game = document.createElement("div");
    game.id = "game";
    expect(resolveBezelHost(game)).toBe(game);
  });

  it("adopts the fullscreen element when it carries the ejs_parent class", () => {
    // EmulatorJS tags its fullscreen container with .ejs_parent.
    const parent = document.createElement("div");
    parent.classList.add("ejs_parent");
    expect(resolveBezelHost(parent)).toBe(parent);
  });

  it("returns null when nothing is fullscreen (windowed → render in place)", () => {
    expect(resolveBezelHost(null)).toBeNull();
  });

  it("ignores an unrelated fullscreen element that is not the emulator", () => {
    const other = document.createElement("div");
    other.id = "something-else";
    expect(resolveBezelHost(other)).toBeNull();
  });
});

describe("resolveStoredBezelVisible", () => {
  it("defaults to visible when nothing is stored", () => {
    expect(resolveStoredBezelVisible(null)).toBe(true);
  });

  it("is hidden only when the user explicitly turned it off", () => {
    expect(resolveStoredBezelVisible("0")).toBe(false);
  });

  it("is visible for the explicit-on marker", () => {
    expect(resolveStoredBezelVisible("1")).toBe(true);
  });

  it("treats any other stored value as visible (fail safe: show)", () => {
    expect(resolveStoredBezelVisible("anything")).toBe(true);
  });
});
