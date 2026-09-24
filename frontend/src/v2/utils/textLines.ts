/**
 * How many lines `text` wraps to in `width` pixels, breaking between words the
 * way the browser does, and inside a word only when it can't fit a line alone.
 *
 * Args:
 *   measure: The width of a run of text in the font it's set in.
 */
export function wrappedLineCount(
  text: string,
  width: number,
  measure: (run: string) => number,
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
    line = w - extra * width;
  }
  return lines;
}

/** Measures text in a CSS `font`, or null where there's no canvas to do it. */
export function canvasMeasure(font: string): ((run: string) => number) | null {
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return null;
  context.font = font;
  return (run) => context.measureText(run).width;
}
