import { describe, expect, it } from "vitest";
import { currentLetterInRange, lettersInRange } from "./index";
import type { GalleryItem } from "./types";

function row(i: number, letters: string[]): GalleryItem {
  return {
    kind: "row",
    key: `r${i}`,
    startPosition: i * 4,
    endPosition: i * 4 + 4,
    letters,
  };
}

// The second row starts with the last S game and runs into T.
const items = [row(0, ["S"]), row(1, ["S", "T"]), row(2, ["T"]), row(3, ["U"])];

describe("lettersInRange", () => {
  it("collects every letter the range covers", () => {
    expect([...lettersInRange(items, 1, 2)]).toEqual(["S", "T"]);
  });

  it("is empty for an empty range", () => {
    expect(lettersInRange(items, 0, -1).size).toBe(0);
  });
});

describe("currentLetterInRange", () => {
  it("marks the picked letter when its row starts with the letter before", () => {
    expect(currentLetterInRange(items, 1, 2, "T")).toBe("T");
  });

  it("falls back to the first letter once the picked one scrolls away", () => {
    expect(currentLetterInRange(items, 3, 3, "T")).toBe("U");
  });

  it("uses the first letter in range when nothing was picked", () => {
    expect(currentLetterInRange(items, 1, 2, null)).toBe("S");
  });

  it("is empty for an empty range", () => {
    expect(currentLetterInRange(items, 0, -1, "T")).toBe("");
  });
});
