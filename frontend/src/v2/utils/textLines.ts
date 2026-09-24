/**
 * How many lines `text` wraps to in `width` pixels, breaking between words the
 * way the browser does, and inside a word only when it can't fit a line alone.
 *
 * Args:
 *   measure: The width of a run of text in the font it's set in.
 *   maxLines: Stops counting here, as a line clamp stops showing.
 */
export function wrappedLineCount(
  text: string,
  width: number,
  measure: (run: string) => number,
  maxLines = Infinity,
): number {
  if (width <= 0) return 1;
  const space = measure(" ");
  let lines = 1;
  let line = 0;
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const w = measure(word);
    const next = line === 0 ? w : line + space + w;
    if (next <= width) {
      line = next;
      continue;
    }
    if (line > 0) lines += 1;
    const extra = Math.max(0, Math.ceil(w / width) - 1);
    lines += extra;
    if (lines >= maxLines) return maxLines;
    line = w - extra * width;
  }
  return lines;
}

let context: CanvasRenderingContext2D | null | undefined;

/**
 * Measures text in a CSS `font`, or null where there's no canvas to do it.
 * Each word is measured once, since names and verbs repeat down a list.
 */
export function canvasMeasure(font: string): ((run: string) => number) | null {
  context ??= document.createElement("canvas").getContext("2d");
  const shared = context;
  if (!shared) return null;
  const widths = new Map<string, number>();
  return (run) => {
    let width = widths.get(run);
    if (width === undefined) {
      shared.font = font;
      width = shared.measureText(run).width;
      widths.set(run, width);
    }
    return width;
  };
}
