import { vi } from "vitest";

/** A transition's `ready`, rejected as the browser rejects a preempted one. */
export function skippedReady(): Promise<void> {
  return Promise.reject(
    new DOMException("Transition was skipped", "AbortError"),
  );
}

// happy-dom has no View Transitions API, so the native call is always stubbed.
// The stub runs the update callback, as the browser does even when it skips.
export function stubStartViewTransition(ready: Promise<void>) {
  const finished = Promise.resolve();
  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    value: vi.fn((callback?: () => Promise<void>) => {
      void callback?.();
      return {
        updateCallbackDone: Promise.resolve(),
        ready,
        finished,
        skipTransition: () => {},
      };
    }),
  });
  return finished;
}
