interface ViewTransition {
  captured: Promise<void>;
  updateCallbackDone: Promise<void>;
  ready: Promise<void>;
  finished: Promise<void>;
  skipTransition: () => void;
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
    viewTransition.ready = nativeViewTransition.ready;
    viewTransition.finished = nativeViewTransition.finished;
    viewTransition.skipTransition =
      nativeViewTransition.skipTransition.bind(nativeViewTransition);
  });
  viewTransition.captured = capturedPromise;

  return viewTransition;
}
