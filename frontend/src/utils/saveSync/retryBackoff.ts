// A poll re-offers a failed upload every tick, which only hammers a server
// that is refusing it or on its way down.
export const RETRY_BACKOFF_MIN_MS = 2_000;
export const RETRY_BACKOFF_MAX_MS = 30_000;

/** Spaces out the retries of a failing upload, doubling the wait up to a cap. */
export function createRetryBackoff(now: () => number = Date.now) {
  let delay = 0;
  let retryAt = 0;
  return {
    ready: (): boolean => now() >= retryAt,
    failed() {
      delay = Math.min(
        Math.max(delay * 2, RETRY_BACKOFF_MIN_MS),
        RETRY_BACKOFF_MAX_MS,
      );
      retryAt = now() + delay;
    },
    reset() {
      delay = 0;
      retryAt = 0;
    },
  };
}
