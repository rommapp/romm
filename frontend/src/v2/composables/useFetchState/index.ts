// useAsyncState with RomM's defaults: a refetch keeps the current data up,
// and callbacks only fire for the newest call so a stale response is ignored.
import { useAsyncState } from "@vueuse/core";
import type { Ref } from "vue";

export interface UseFetchStateOptions<T> {
  /** Run the fetcher on setup. Defaults to true; turn off when it needs args. */
  immediate?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: unknown) => void;
}

export interface UseFetchState<T, Args extends unknown[]> {
  state: Ref<T>;
  isLoading: Ref<boolean>;
  /** The newest call's error, cleared when the next call starts. */
  error: Ref<unknown>;
  execute: (...args: Args) => Promise<T | undefined>;
}

export function useFetchState<T, Args extends unknown[] = []>(
  fetcher: (...args: Args) => Promise<T>,
  initial: T,
  options: UseFetchStateOptions<T> = {},
): UseFetchState<T, Args> {
  let latest = 0;

  const { state, isLoading, error, executeImmediate } = useAsyncState(
    async (...args: Args) => {
      const call = ++latest;
      try {
        const data = await fetcher(...args);
        if (call === latest) options.onSuccess?.(data);
        return data;
      } catch (err) {
        if (call === latest) options.onError?.(err);
        throw err;
      }
    },
    initial,
    {
      immediate: options.immediate ?? true,
      resetOnExecute: false,
      onError: () => {},
    },
  );

  return { state, isLoading, error, execute: executeImmediate };
}
