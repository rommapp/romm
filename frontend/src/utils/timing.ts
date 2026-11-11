export interface Cancelable {
  /** Drop any pending call. */
  cancel: () => void;
}

export interface DebouncedFn<A extends unknown[]> extends Cancelable {
  (...args: A): void;
  /** Run the pending call now, if there is one. */
  flush: () => void;
}

/**
 * Trailing-edge debounce: `fn` runs `wait` ms after the last call, with the
 * last call's arguments. `maxWait` caps how long a steady stream of calls can
 * keep postponing it.
 */
export function debounce<A extends unknown[]>(
  fn: (...args: A) => void,
  wait: number,
  { maxWait }: { maxWait?: number } = {},
): DebouncedFn<A> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let maxTimer: ReturnType<typeof setTimeout> | undefined;
  let pending: A | undefined;

  const cancel = () => {
    clearTimeout(timer);
    clearTimeout(maxTimer);
    timer = maxTimer = undefined;
    pending = undefined;
  };

  const flush = () => {
    const args = pending;
    cancel();
    if (args) fn(...args);
  };

  const debounced = (...args: A) => {
    pending = args;
    clearTimeout(timer);
    timer = setTimeout(flush, wait);
    if (maxWait !== undefined && maxTimer === undefined) {
      maxTimer = setTimeout(flush, maxWait);
    }
  };

  return Object.assign(debounced, { cancel, flush });
}

export interface ThrottledFn<A extends unknown[]> extends Cancelable {
  (...args: A): void;
}

/**
 * Throttle that fires on the leading edge, then at most once per `wait` ms,
 * with a trailing call carrying the latest arguments.
 */
export function throttle<A extends unknown[]>(
  fn: (...args: A) => void,
  wait: number,
): ThrottledFn<A> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lastRun = -Infinity;
  let pending: A | undefined;

  const run = (args: A) => {
    lastRun = Date.now();
    fn(...args);
  };

  const cancel = () => {
    clearTimeout(timer);
    timer = undefined;
    pending = undefined;
  };

  const throttled = (...args: A) => {
    const remaining = wait - (Date.now() - lastRun);
    if (remaining <= 0 || remaining > wait) {
      cancel();
      run(args);
      return;
    }
    pending = args;
    timer ??= setTimeout(() => {
      const next = pending;
      cancel();
      if (next) run(next);
    }, remaining);
  };

  return Object.assign(throttled, { cancel });
}
