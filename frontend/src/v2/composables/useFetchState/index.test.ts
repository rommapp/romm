import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, type EffectScope } from "vue";
import { useFetchState, type UseFetchStateOptions } from "./index";

const scopes: EffectScope[] = [];

function setup<T, Args extends unknown[] = []>(
  fetcher: (...args: Args) => Promise<T>,
  initial: T,
  options?: UseFetchStateOptions<T>,
) {
  const scope = effectScope();
  scopes.push(scope);
  return scope.run(() => useFetchState(fetcher, initial, options))!;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useFetchState", () => {
  afterEach(() => {
    scopes.splice(0).forEach((scope) => scope.stop());
  });

  it("fetches on setup and exposes the result", async () => {
    const onSuccess = vi.fn();
    const fetcher = vi.fn(() => Promise.resolve([1, 2]));
    const fetch = setup(fetcher, [] as number[], { onSuccess });

    expect(fetch.isLoading.value).toBe(true);
    await vi.waitFor(() => expect(fetch.isLoading.value).toBe(false));

    expect(fetch.state.value).toEqual([1, 2]);
    expect(fetch.isLoading.value).toBe(false);
    expect(onSuccess).toHaveBeenCalledWith([1, 2]);
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("waits for execute when immediate is off and passes its args", async () => {
    const fetcher = vi.fn((id: number) => Promise.resolve(id * 2));
    const fetch = setup(fetcher, 0, { immediate: false });

    expect(fetcher).not.toHaveBeenCalled();
    await fetch.execute(21);

    expect(fetcher).toHaveBeenCalledWith(21);
    expect(fetch.state.value).toBe(42);
  });

  it("keeps the current data while a refetch is in flight", async () => {
    const next = deferred<string>();
    const fetcher = vi
      .fn<() => Promise<string>>()
      .mockResolvedValueOnce("first")
      .mockReturnValueOnce(next.promise);
    const fetch = setup(fetcher, "", { immediate: false });
    await fetch.execute();

    const refetch = fetch.execute();
    expect(fetch.isLoading.value).toBe(true);
    expect(fetch.state.value).toBe("first");

    next.resolve("second");
    await refetch;
    expect(fetch.state.value).toBe("second");
  });

  it("ignores a stale response and its callbacks", async () => {
    const older = deferred<string>();
    const onSuccess = vi.fn();
    const fetcher = vi
      .fn<() => Promise<string>>()
      .mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce("newer");
    const fetch = setup(fetcher, "", { immediate: false, onSuccess });

    const stale = fetch.execute();
    await fetch.execute();
    older.resolve("older");
    await stale;

    expect(fetch.state.value).toBe("newer");
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(onSuccess).toHaveBeenCalledWith("newer");
  });

  it("reports the newest failure through error and onError", async () => {
    const failure = new Error("boom");
    const onError = vi.fn();
    const fetch = setup(() => Promise.reject(failure), "kept", { onError });
    await vi.waitFor(() => expect(fetch.isLoading.value).toBe(false));

    expect(fetch.error.value).toBe(failure);
    expect(fetch.state.value).toBe("kept");
    expect(onError).toHaveBeenCalledWith(failure);
  });

  it("drops the error of a superseded call", async () => {
    const older = deferred<string>();
    const onError = vi.fn();
    const fetcher = vi
      .fn<() => Promise<string>>()
      .mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce("newer");
    const fetch = setup(fetcher, "", { immediate: false, onError });

    const stale = fetch.execute();
    await fetch.execute();
    older.reject(new Error("late"));
    await stale;

    expect(onError).not.toHaveBeenCalled();
    expect(fetch.error.value).toBeUndefined();
  });
});
