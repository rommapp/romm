// Geometry for useSpatialNav's arrow-key moves between arbitrary controls.

// Elements that take part in keyboard and pad navigation. `tabindex="-1"`
// is left out so roving-tabindex grids expose only their current cell.
export const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]",
]
  .map((selector) => `${selector}:not([tabindex='-1'])`)
  .join(",");

export type SpatialDirection = "up" | "down" | "left" | "right";

export const ARROW_DIRECTIONS: Record<string, SpatialDirection | undefined> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
};

type Box = Pick<DOMRect, "top" | "bottom" | "left" | "right">;

// Absorbs sub-pixel rounding and 1px negative margins between neighbours.
const EDGE_TOLERANCE = 2;
// Sideways offset costs more than distance along the move, so the control
// straight ahead beats a nearer one off to the side.
const ORTHO_WEIGHT = 2;
// Among candidates that all overlap sideways, prefer the best centred one.
const CENTER_WEIGHT = 0.1;
// Larger than any on-screen score, so it ranks diagonals after the rest.
const DIAGONAL_PENALTY = 1e6;

// Projects both boxes so "down" is the primary axis, whatever `dir` is.
function project(box: Box, dir: SpatialDirection) {
  switch (dir) {
    case "down":
      return { start: box.top, end: box.bottom, lo: box.left, hi: box.right };
    case "up":
      return { start: -box.bottom, end: -box.top, lo: box.left, hi: box.right };
    case "right":
      return { start: box.left, end: box.right, lo: box.top, hi: box.bottom };
    case "left":
      return { start: -box.right, end: -box.left, lo: box.top, hi: box.bottom };
  }
}

/**
 * Scores how far `to` is from `from` when moving in `dir`.
 *
 * Returns:
 *   A lower-is-closer score, or null when `to` does not lie in that direction.
 */
export function spatialScore(
  from: Box,
  to: Box,
  dir: SpatialDirection,
): number | null {
  const a = project(from, dir);
  const b = project(to, dir);
  const beyondEdge = b.start >= a.end - EDGE_TOLERANCE;
  const centreBeyondEdge = (b.start + b.end) / 2 >= a.end;
  if (!beyondEdge && !centreBeyondEdge) return null;
  const gap = Math.max(0, b.start - a.end);
  const orthoGap = Math.max(0, b.lo - a.hi, a.lo - b.hi);
  const centreOffset = Math.abs((b.lo + b.hi) / 2 - (a.lo + a.hi) / 2);
  const score = gap + orthoGap * ORTHO_WEIGHT + centreOffset * CENTER_WEIGHT;
  // A candidate outside the 45 degree cone is a diagonal: taken only when
  // nothing lies inside it, such as a top bar off to one side.
  return orthoGap > gap ? score + DIAGONAL_PENALTY : score;
}

/** The candidate closest to `from` in `dir`, or null when none lies that way. */
export function pickSpatialTarget<T>(
  from: Box,
  candidates: { item: T; box: Box }[],
  dir: SpatialDirection,
): T | null {
  let best: T | null = null;
  let bestScore = Infinity;
  for (const { item, box } of candidates) {
    const score = spatialScore(from, box, dir);
    if (score !== null && score < bestScore) {
      best = item;
      bestScore = score;
    }
  }
  return best;
}
