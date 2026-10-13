// A paused clip keeps its request open too, so only the clip played last may
// hold one.
let current: { el: HTMLMediaElement; onRelease: () => void } | null = null;

// Dropping the src aborts the in-flight request; pause() alone keeps it open
// and ties up a browser connection.
export function releaseMedia(el: HTMLMediaElement) {
  if (current?.el === el) current = null;
  el.pause();
  el.removeAttribute("src");
  el.load();
}

// Call when a clip starts playing. The clip played before it is released, and
// its owner makes it playable again (onRelease).
export function claimMedia(el: HTMLMediaElement, onRelease: () => void) {
  const previous = current;
  current = { el, onRelease };
  if (!previous || previous.el === el) return;
  releaseMedia(previous.el);
  previous.onRelease();
}
