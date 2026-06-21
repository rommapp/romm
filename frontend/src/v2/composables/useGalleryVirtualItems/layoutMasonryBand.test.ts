import { describe, expect, it } from "vitest";
import { layoutMasonryBand } from "./index";

// Card full height = cardWidth / ratio + 23 (label chrome). With ratio 1
// and cardWidth 100 each card is 123px tall; stacking adds an 18px gap.
const SQUARE = () => 1; // 100 / 1 + 23 = 123 per card
const WIDTH = 100;

describe("layoutMasonryBand", () => {
  it("spreads positions across columns shortest-first (round-robin when equal)", () => {
    const { columns } = layoutMasonryBand([0, 1, 2, 3, 4, 5], 3, WIDTH, SQUARE);
    // Equal-height cards → each column gets every Nth position.
    expect(columns).toEqual([
      [0, 3],
      [1, 4],
      [2, 5],
    ]);
  });

  it("reports the tallest column as the band height", () => {
    // 4 equal cards over 3 columns → tallest column has 2 cards:
    // 123 + 18 + 123 = 264.
    const { height } = layoutMasonryBand([0, 1, 2, 3], 3, WIDTH, SQUARE);
    expect(height).toBeCloseTo(264);
  });

  it("packs a tall card's column less so shorter cards balance it", () => {
    // Position 0 is very tall (ratio 0.5 → 200+23=223), the rest square
    // (123). Shortest-first keeps stacking the short column until it
    // catches up, so column 0 (the tall one) gets fewer cards.
    const ratioAt = (p: number) => (p === 0 ? 0.5 : 1);
    const { columns } = layoutMasonryBand([0, 1, 2, 3], 2, WIDTH, ratioAt);
    // col0: [0] (223). col1 fills until it passes 223: 123,+18+123=264.
    expect(columns[0]).toEqual([0, 3]);
    expect(columns[1]).toEqual([1, 2]);
  });

  it("clamps to a single column when cols < 1", () => {
    const { columns } = layoutMasonryBand([0, 1], 0, WIDTH, SQUARE);
    expect(columns).toHaveLength(1);
    expect(columns[0]).toEqual([0, 1]);
  });

  it("falls back to the default ratio for non-positive ratios", () => {
    // ratio 0 → falls back to 2/3, so height = 100/(2/3)+23 = 173.
    const { height } = layoutMasonryBand([0], 1, WIDTH, () => 0);
    expect(height).toBeCloseTo(100 / (2 / 3) + 23);
  });
});
