import { describe, expect, it } from "vitest";
import { packFlowRows } from "./index";

// Card width = H * ratio. H=100, GAP=12 → a square card is 100px wide.
const SQUARE = () => 1;
const H = 100;
const GAP = 12;

describe("packFlowRows", () => {
  it("fills a row until the next card would overflow, then wraps", () => {
    // Row 340: 100+12+100+12+100=324 fits, a 4th overflows → 3 per row.
    const rows = packFlowRows(0, 7, 340, H, GAP, SQUARE);
    expect(rows).toEqual([
      { start: 0, end: 3 },
      { start: 3, end: 6 },
      { start: 6, end: 7 },
    ]);
  });

  it("packs more, narrower cards per row when covers are portrait", () => {
    // Portrait 0.5 → 50px wide; all 5 fit in 340.
    const rows = packFlowRows(0, 5, 340, H, GAP, () => 0.5);
    expect(rows).toEqual([{ start: 0, end: 5 }]);
  });

  it("gives an over-wide card its own row instead of an empty one", () => {
    // ratio 4 → 400px wide > row 340 → each alone.
    const rows = packFlowRows(0, 2, 340, H, GAP, () => 4);
    expect(rows).toEqual([
      { start: 0, end: 1 },
      { start: 1, end: 2 },
    ]);
  });

  it("mixes widths within a row by running natural width", () => {
    // widths 50,200,50,50: first 3 = 324 fit, 4th wraps.
    const ratioAt = (p: number) => (p === 1 ? 2 : 0.5);
    const rows = packFlowRows(0, 4, 340, H, GAP, ratioAt);
    expect(rows).toEqual([
      { start: 0, end: 3 },
      { start: 3, end: 4 },
    ]);
  });

  it("returns nothing for an empty range", () => {
    expect(packFlowRows(5, 5, 340, H, GAP, SQUARE)).toEqual([]);
  });
});
