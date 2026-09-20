// A minimal ease-out tween over requestAnimationFrame, shared by the two
// places that animate a number Vue renders (a rolling count, a panel's
// height). Not a composable: it takes the duration already resolved, so
// reduced motion and the motion tokens stay the caller's business.

function easeOut(t: number): number {
  return 1 - (1 - t) ** 3;
}

interface TweenOptions {
  from: number;
  to: number;
  /** 0 lands on `to` synchronously, which is what reduced motion wants. */
  durationMs: number;
  onUpdate: (value: number) => void;
  onDone?: () => void;
}

/** Starts the tween and returns the function that cancels it. */
export function tween({
  from,
  to,
  durationMs,
  onUpdate,
  onDone,
}: TweenOptions): () => void {
  if (durationMs <= 0) {
    onUpdate(to);
    onDone?.();
    return () => {};
  }

  let frame: number | null = null;
  const cancel = () => {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
  };

  // Paint the starting value now: the first frame is a whole render away,
  // and in a background tab it never comes at all.
  onUpdate(from);
  const start = performance.now();
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / durationMs);
    if (t < 1) {
      onUpdate(from + (to - from) * easeOut(t));
      frame = requestAnimationFrame(step);
      return;
    }
    onUpdate(to);
    frame = null;
    onDone?.();
  };
  frame = requestAnimationFrame(step);

  return cancel;
}
