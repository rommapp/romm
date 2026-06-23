import { describe, expect, it } from "vitest";
import { assignFlatRowLetters } from "./index";

// Reference (the pre-restructure per-row scan) — each row collects every range
// it overlaps. The linear `assignFlatRowLetters` must match this exactly.
function naive(
  rows: ReadonlyArray<{ start: number; end: number }>,
  ranges: ReadonlyArray<{ letter: string; start: number; end: number }>,
): string[][] {
  return rows.map((row) =>
    ranges
      .filter((r) => r.end > row.start && r.start < row.end)
      .map((r) => r.letter),
  );
}

describe("assignFlatRowLetters", () => {
  // Letters partition the positions: A[0,4) B[4,9) C[9,12).
  const ranges = [
    { letter: "A", start: 0, end: 4 },
    { letter: "B", start: 4, end: 9 },
    { letter: "C", start: 9, end: 12 },
  ];

  it("tags a row fully inside one letter with just that letter", () => {
    expect(assignFlatRowLetters([{ start: 0, end: 3 }], ranges)).toEqual([
      ["A"],
    ]);
  });

  it("tags a row straddling a boundary with both letters", () => {
    // [2,6) overlaps A[0,4) and B[4,9).
    expect(assignFlatRowLetters([{ start: 2, end: 6 }], ranges)).toEqual([
      ["A", "B"],
    ]);
  });

  it("tags a row spanning three letters with all three", () => {
    expect(assignFlatRowLetters([{ start: 3, end: 12 }], ranges)).toEqual([
      ["A", "B", "C"],
    ]);
  });

  it("advances correctly across many consecutive rows", () => {
    const rows = [
      { start: 0, end: 3 }, // A
      { start: 3, end: 5 }, // A,B
      { start: 5, end: 9 }, // B
      { start: 9, end: 12 }, // C
    ];
    expect(assignFlatRowLetters(rows, ranges)).toEqual([
      ["A"],
      ["A", "B"],
      ["B"],
      ["C"],
    ]);
  });

  it("matches the naive per-row scan on a denser layout", () => {
    const rows = [
      { start: 0, end: 2 },
      { start: 2, end: 4 },
      { start: 4, end: 4 }, // empty row (degenerate) → no letters
      { start: 4, end: 11 },
      { start: 11, end: 12 },
    ];
    expect(assignFlatRowLetters(rows, ranges)).toEqual(naive(rows, ranges));
  });

  it("returns empties when there are no ranges", () => {
    expect(assignFlatRowLetters([{ start: 0, end: 3 }], [])).toEqual([[]]);
  });
});
