// useAsyncState with RomM's defaults: a refetch keeps the current data up,
// and callbacks only fire for the newest call so a stale response is ignored.
import { useAsyncState } from "@vueuse/core";
import type { Ref } from "vue";

export interface UseFetchStateOptions<T> {
  /** Run the fetcher on setup. Defaults to true. */
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

export function useFetchState<T>(
  fetcher: () => Promise<T>,
  initial: T,
  options?: UseFetchStateOptions<T>,
): UseFetchState<T, []>;
// A fetcher that takes arguments can't run on setup, so it must opt out.
export function useFetchState<T, Args extends unknown[]>(
  fetcher: (...args: Args) => Promise<T>,
  initial: T,
  options: UseFetchStateOptions<T> & { immediate: false },
): UseFetchState<T, Args>;
export function useFetchState<T>(
  fetcher: (...args: unknown[]) => Promise<T>,
  initial: T,
  options: UseFetchStateOptions<T> = {},
): UseFetchState<T, unknown[]> {
  const { state, isLoading, error, executeImmediate } = useAsyncState(
    fetcher,
    initial,
    { immediate: false, resetOnExecute: false, onError: () => {} },
  );

  let latest = 0;

  // Callbacks run after the newest call has written `state` and `error`.
  async function execute(...args: unknown[]): Promise<T | undefined> {
    const call = ++latest;
    const data = await executeImmediate(...args);
    if (call !== latest) return data;
    if (error.value !== undefined) options.onError?.(error.value);
    else options.onSuccess?.(data as T);
    return data;
  }

  if (options.immediate ?? true) void execute();

  return { state, isLoading, error, execute };
}
