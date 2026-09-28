// The selection bar, the hill carrying the count and the fillets between them
// are three separate fills, so no per-box border can trace their union: the
// arcs and the hill's sides are measured from different edges and meet at a
// kink. One path over the lot is the only line that closes.

/** Overlap of the hill's foot into the bar; matches `bottom` in the CSS. */
export const NOTCH_OVERLAP_PX = 6;
/** Radius of the concave corner where the hill meets the bar. */
export const FILLET_PX = 12;
// A pill radius would grow with the digits until the hill's sides curved all
// the way into the bar, leaving the fillets, which meet a straight side,
// nothing to sit against. A fixed one keeps the shape whatever the count.
/** Radius over the hill's top corners. */
export const NOTCH_RADIUS_PX = 14;

interface Box {
  w: number;
  h: number;
}

export interface Outline {
  width: number;
  height: number;
  /** How far the hill stands above the bar's top edge. */
  rise: number;
  d: string;
}

/** The stroke around bar, hill and fillets, or null while either is unmeasured
 *  or too small to carry the shape. */
export function selectionBarOutline(bar: Box, notch: Box): Outline | null {
  const rise = Math.max(0, notch.h - NOTCH_OVERLAP_PX);
  if (bar.w <= 0 || bar.h <= 0 || notch.w <= 0 || rise <= 0) return null;

  const r = bar.h / 2;
  const hillR = Math.min(NOTCH_RADIUS_PX, notch.w / 2, rise);
  // The fillet meets the hill's side below its corner, so it cannot be taller
  // than the straight run between the two.
  const f = Math.min(FILLET_PX, (bar.w - notch.w) / 2 - r, rise - hillR);
  const left = (bar.w - notch.w) / 2;
  const right = left + notch.w;
  const bottom = rise + bar.h;
  if (f <= 0 || rise - f <= 0 || left - f <= r) return null;

  return {
    width: bar.w,
    height: bottom,
    rise,
    d: [
      `M ${r} ${rise}`,
      `H ${left - f}`,
      `A ${f} ${f} 0 0 0 ${left} ${rise - f}`,
      `V ${hillR}`,
      `A ${hillR} ${hillR} 0 0 1 ${left + hillR} 0`,
      `H ${right - hillR}`,
      `A ${hillR} ${hillR} 0 0 1 ${right} ${hillR}`,
      `V ${rise - f}`,
      `A ${f} ${f} 0 0 0 ${right + f} ${rise}`,
      `H ${bar.w - r}`,
      `A ${r} ${r} 0 0 1 ${bar.w - r} ${bottom}`,
      `H ${r}`,
      `A ${r} ${r} 0 0 1 ${r} ${rise}`,
      "Z",
    ].join(" "),
  };
}
