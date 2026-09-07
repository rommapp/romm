/** One state in a multi-state RCheckbox cycle. The first entry is the
 *  "empty" / unchecked state (no fill, no glyph); later states fill the
 *  box with `color` and show `icon` — or the check tick when `icon` is
 *  omitted. The control cycles through the array in order on each click. */
export interface RCheckboxState {
  /** Stable identifier — the value read from / emitted via `stateValue`. */
  value: string;
  /** mdi icon for this state. Omit to show the built-in check tick. */
  icon?: string;
  /** Tone keyword or CSS colour for the box fill. Omit on the first state. */
  color?: string;
}
