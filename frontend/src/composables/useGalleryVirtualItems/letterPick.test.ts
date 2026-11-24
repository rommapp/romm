import { describe, expect, it } from "vitest";
import {
  currentLetterIn,
  lettersInRange,
  settleLetterPick,
  type LetterPick,
} from "./index";
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
const visible = (first: number, last: number) =>
  lettersInRange(items, first, last);

describe("lettersInRange", () => {
  it("collects every letter the range covers, in screen order", () => {
    expect([...visible(1, 2)]).toEqual(["S", "T"]);
  });

  it("is empty for an empty range", () => {
    expect(visible(0, -1).size).toBe(0);
  });
});

describe("currentLetterIn", () => {
  const pickT: LetterPick = { letter: "T", shown: true };

  it("marks the picked letter when its row starts with the letter before", () => {
    expect(currentLetterIn(visible(1, 2), pickT)).toBe("T");
  });

  it("uses the first letter on screen when nothing was picked", () => {
    expect(currentLetterIn(visible(1, 2), null)).toBe("S");
  });

  it("uses the first letter on screen once the pick is off screen", () => {
    expect(currentLetterIn(visible(3, 3), pickT)).toBe("U");
  });

  it("is empty for an empty range", () => {
    expect(currentLetterIn(visible(0, -1), pickT)).toBe("");
  });
});

describe("settleLetterPick", () => {
  it("keeps a pick whose jump has not landed yet", () => {
    const pick = { letter: "T", shown: false };
    expect(settleLetterPick(pick, visible(0, 0))).toBe(pick);
  });

  it("drops the pick after scrolling away, so scrolling back marks S", () => {
    let pick = settleLetterPick({ letter: "T", shown: false }, visible(1, 2));
    expect(pick).toEqual({ letter: "T", shown: true });

    pick = settleLetterPick(pick, visible(3, 3));
    expect(pick).toBeNull();

    expect(currentLetterIn(visible(1, 2), pick)).toBe("S");
  });
});
