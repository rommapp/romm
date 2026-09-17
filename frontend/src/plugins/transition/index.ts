interface ViewTransition {
  captured: Promise<void>;
  updateCallbackDone: Promise<void>;
  ready: Promise<void>;
  finished: Promise<void>;
  skipTransition: () => void;
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
  const callbackPromise = callback
    ? Promise.resolve(callback())
    : Promise.resolve();

  const viewTransition = {
    captured: Promise.resolve(),
    updateCallbackDone: callbackPromise,
    ready: callbackPromise,
    finished: callbackPromise,
    skipTransition: () => {},
  };

  if (!document.startViewTransition) {
    return viewTransition;
  }

  const capturedPromise = new Promise<void>((resolve) => {
    const nativeViewTransition = document.startViewTransition(async () => {
      resolve();
      if (callback) {
        await callback();
      }
    });
    viewTransition.updateCallbackDone = nativeViewTransition.updateCallbackDone;
    viewTransition.ready = absorbPreemptionSkip(nativeViewTransition.ready);
    viewTransition.finished = nativeViewTransition.finished;
    viewTransition.skipTransition =
      nativeViewTransition.skipTransition.bind(nativeViewTransition);
  });
  viewTransition.captured = capturedPromise;

  return viewTransition;
}
