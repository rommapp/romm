export interface ThrottledFn<A extends unknown[]> {
  (...args: A): void;
  /** Drop any pending trailing call. */
  cancel: () => void;
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
