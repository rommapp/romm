import { describe, expect, it } from "vitest";
import { packFlowRows } from "./index";

// Card width = cardHeight * ratio. With cardHeight 100 and ratio 1 each
// card is 100px wide; a 12px gap sits between cards in a row.
const SQUARE = () => 1; // 100px wide per card
const H = 100;
const GAP = 12;

describe("packFlowRows", () => {
  it("fills a row until the next card would overflow, then wraps", () => {
    // Row width 340: card(100) +12+100 +12+100 = 324 fits; a 4th (+12+100)
    // = 436 > 340 → wraps. So 3 per row.
    const rows = packFlowRows(0, 7, 340, H, GAP, SQUARE);
    expect(rows).toEqual([
      { start: 0, end: 3 },
      { start: 3, end: 6 },
      { start: 6, end: 7 },
    ]);
  });

  it("packs more, narrower cards per row when covers are portrait", () => {
    // Portrait 0.5 → 50px wide. Row 340: 50,+12+50(112),+62(174),+62(236),
    // +62(298),+62(360>340 stop) → 5 per row.
    const rows = packFlowRows(0, 5, 340, H, GAP, () => 0.5);
    expect(rows).toEqual([{ start: 0, end: 5 }]);
  });

  it("gives an over-wide card its own row instead of an empty one", () => {
    // ratio 4 → 400px wide > row 340. Each lands alone.
    const rows = packFlowRows(0, 2, 340, H, GAP, () => 4);
    expect(rows).toEqual([
      { start: 0, end: 1 },
      { start: 1, end: 2 },
    ]);
  });

  it("mixes widths within a row by running natural width", () => {
    const ratioAt = (p: number) => (p === 1 ? 2 : 0.5); // 50,200,50,50
    // Row 340: p0=50; +12+200=262; +12+50=324; +12+50=386>340 → wrap.
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
