import { describe, expect, it } from "vitest";
import { colorCoverArt } from "@/v2/tokens";
import {
  coverPlaceholderArt,
  getMissingCoverImage,
  getUnmatchedCoverImage,
} from "./covers";

describe("cover placeholder art", () => {
  it("returns an inline SVG data URI", () => {
    const uri = getMissingCoverImage("Chrono Trigger");
    expect(uri.startsWith("data:image/svg+xml,")).toBe(true);
    expect(decodeURIComponent(uri)).toContain("<svg");
  });

  it("is deterministic per name", () => {
    expect(getMissingCoverImage("Sonic")).toBe(getMissingCoverImage("Sonic"));
    expect(getUnmatchedCoverImage("Sonic")).toBe(
      getUnmatchedCoverImage("Sonic"),
    );
  });

  it("varies the art between different names", () => {
    expect(getMissingCoverImage("Mario")).not.toBe(
      getMissingCoverImage("Zelda"),
    );
  });

  it("uses the tokenised palette, not raw hex", () => {
    const svg = decodeURIComponent(getMissingCoverImage("Metroid"));
    expect(svg).toContain(colorCoverArt.base);
    expect(svg).toContain(colorCoverArt.warm);
    expect(svg).toContain(colorCoverArt.icon);
  });

  it("missing (grid) and unmatched (question mark) icons differ", () => {
    expect(getMissingCoverImage("Kirby")).not.toBe(
      getUnmatchedCoverImage("Kirby"),
    );
  });

  it("coverPlaceholderArt routes identified→missing, else→unmatched", () => {
    expect(coverPlaceholderArt("Tetris", true)).toBe(
      getMissingCoverImage("Tetris"),
    );
    expect(coverPlaceholderArt("Tetris", false)).toBe(
      getUnmatchedCoverImage("Tetris"),
    );
  });
});
