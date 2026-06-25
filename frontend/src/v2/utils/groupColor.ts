// Curated palette for permission group colors. Groups render as colored
// pills/dots in the admin UI; the value stored on the group is a hex string
// from this palette (a discrete "color picker").
export const GROUP_COLOR_PALETTE = [
  "#7c5cff",
  "#3b82f6",
  "#06b6d4",
  "#10b981",
  "#84cc16",
  "#f59e0b",
  "#f97316",
  "#ef4444",
  "#ec4899",
  "#8b5cf6",
  "#64748b",
] as const;

export const DEFAULT_GROUP_COLOR = "#64748b";

/** A group's color, falling back to a neutral when none is set. */
export function groupColor(color: string | null | undefined): string {
  return color || DEFAULT_GROUP_COLOR;
}
