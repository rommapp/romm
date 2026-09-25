import { describe, expect, it } from "vitest";
import { NOTCH_RADIUS_PX, selectionBarOutline } from "./selectionBarOutline";

const BAR = { w: 375, h: 48 };
/** The hill as one digit and as four measure on screen. */
const ONE_DIGIT = { w: 39, h: 35 };
const FOUR_DIGITS = { w: 61, h: 35 };

/** Every radius the path arcs on, in the order it draws them. */
function radii(d: string): number[] {
  return [...d.matchAll(/A (\d+(?:\.\d+)?) /g)].map((a) => Number(a[1]));
}

describe("selectionBarOutline", () => {
  // The fill rounds the hill's top corners by a fixed radius, so a count that
  // widens the hill must not widen the arc the stroke draws over them.
  it("rounds the hill by the same radius whatever the count", () => {
    const one = radii(selectionBarOutline(BAR, ONE_DIGIT)!.d);
    const four = radii(selectionBarOutline(BAR, FOUR_DIGITS)!.d);

    // Fillet, both hill corners, fillet, then the bar's own two ends.
    expect(one).toEqual([12, NOTCH_RADIUS_PX, NOTCH_RADIUS_PX, 12, 24, 24]);
    expect(four).toEqual(one);
  });

  it("runs the hill's sides straight from its corners into the fillets", () => {
    const { d } = selectionBarOutline(BAR, FOUR_DIGITS)!;

    // Down to the corner's start, and back up from the far one: the fillets
    // sit against a straight side rather than part-way around a curve.
    expect(d).toContain(`V ${NOTCH_RADIUS_PX}`);
    expect(d).toContain("V 17");
  });

  it("stands the hill on the bar, less the foot it sinks into it", () => {
    const outline = selectionBarOutline(BAR, FOUR_DIGITS)!;

    expect(outline.rise).toBe(29);
    expect(outline.height).toBe(29 + BAR.h);
    expect(outline.width).toBe(BAR.w);
  });

  it("keeps the hill's corners inside a hill narrower than them", () => {
    const narrow = { w: 20, h: 35 };

    expect(radii(selectionBarOutline(BAR, narrow)!.d)).toEqual([
      12, 10, 10, 12, 24, 24,
    ]);
  });

  it("draws nothing until both boxes are measured", () => {
    expect(selectionBarOutline({ w: 0, h: 0 }, FOUR_DIGITS)).toBeNull();
    expect(selectionBarOutline(BAR, { w: 0, h: 0 })).toBeNull();
  });

  // The fillets need room between the hill and the bar's rounded end.
  it("draws nothing where the hill fills the bar", () => {
    expect(selectionBarOutline(BAR, { w: BAR.w - 10, h: 35 })).toBeNull();
  });
});
