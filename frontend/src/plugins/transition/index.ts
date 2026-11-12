interface ViewTransition {
  captured: Promise<void>;
  updateCallbackDone: Promise<void>;
  ready: Promise<void>;
  finished: Promise<void>;
  skipTransition: () => void;
}

// A running view transition swallows every tap, so a tab-bar tap swaps the
// view instantly (as native tab bars do) to keep the next tap live.
let instantPath: string | null = null;

/** Skip the view transition of the next navigation to `fullPath`. */
export function skipTransitionTo(fullPath: string): void {
  instantPath = fullPath;
}

export function isTransitionSkipped(to: { fullPath: string }): boolean {
  return to.fullPath === instantPath;
}

/** Drops the skip when a navigation elsewhere (a redirect included) supersedes it. */
export function dropSupersededSkip(to: { fullPath: string }): void {
  if (to.fullPath !== instantPath) instantPath = null;
}

/** Drops the skip once its navigation has ended, however it ended. */
export function settleSkippedTransition(to: { fullPath: string }): void {
  if (to.fullPath === instantPath) instantPath = null;
}

// A transition the browser preempts is skipped, which rejects `ready` with
// AbortError. Rethrow anything else so real transition failures stay visible.
export function absorbPreemptionSkip(ready: Promise<void>): Promise<void> {
  return ready.catch((reason: unknown) => {
    if (!(reason instanceof DOMException && reason.name === "AbortError")) {
      throw reason;
    }
  });
}

export function startViewTransition(
  callback?: () => Promise<void>,
): ViewTransition {
  if (!document.startViewTransition) {
    const callbackPromise = callback ? callback() : Promise.resolve();
    return {
      // Nothing is snapshotted without the API, so callers need not wait.
      captured: Promise.resolve(),
      updateCallbackDone: callbackPromise,
      ready: callbackPromise,
      finished: callbackPromise,
      skipTransition: () => {},
    };
  }

  // Resolved from inside the update callback, which the browser runs once the
  // old state is captured.
  let resolveCaptured!: () => void;
  const captured = new Promise<void>((resolve) => {
    resolveCaptured = resolve;
  });

  const nativeViewTransition = document.startViewTransition(async () => {
    resolveCaptured();
    if (callback) {
      await callback();
    }
  });

  return {
    captured,
    updateCallbackDone: nativeViewTransition.updateCallbackDone,
    ready: absorbPreemptionSkip(nativeViewTransition.ready),
    finished: nativeViewTransition.finished,
    skipTransition:
      nativeViewTransition.skipTransition.bind(nativeViewTransition),
  };
}
