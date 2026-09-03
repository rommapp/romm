import { AxiosError, type AxiosResponse } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope } from "vue";
import { useTaskCompletion } from "./index";

const { getTaskById } = vi.hoisted(() => ({ getTaskById: vi.fn() }));

vi.mock("@/services/api/task", () => ({ default: { getTaskById } }));

const status = (s: string) => ({ data: { status: s } });

const httpError = (code: number) =>
  new AxiosError("boom", undefined, undefined, undefined, {
    status: code,
  } as AxiosResponse);

// The composable registers an onScopeDispose hook, so it needs an owning scope
// the same way a component setup would give it one.
function inScope() {
  const scope = effectScope();
  const composable = scope.run(() => useTaskCompletion())!;
  return { ...composable, dispose: () => scope.stop() };
}

describe("useTaskCompletion", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getTaskById.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves without waiting when the job already finished", async () => {
    getTaskById.mockResolvedValue(status("finished"));

    const { awaitTask } = inScope();
    await expect(awaitTask("job-1")).resolves.toBe(true);
    expect(getTaskById).toHaveBeenCalledTimes(1);
  });

  it("keeps polling while the job is queued or running", async () => {
    getTaskById
      .mockResolvedValueOnce(status("queued"))
      .mockResolvedValueOnce(status("started"))
      .mockResolvedValueOnce(status("finished"));

    const { awaitTask } = inScope();
    const settled = awaitTask("job-1");

    await vi.advanceTimersByTimeAsync(5000);

    await expect(settled).resolves.toBe(true);
    expect(getTaskById).toHaveBeenCalledTimes(3);
  });

  // The job ran and its result has already aged out of Redis, so there is
  // nothing left to wait for.
  it("treats an unfetchable job as done", async () => {
    getTaskById.mockRejectedValue(httpError(404));

    const { awaitTask } = inScope();
    await expect(awaitTask("job-1")).resolves.toBe(true);
  });

  it("keeps polling through a transient failure", async () => {
    getTaskById
      .mockRejectedValueOnce(httpError(503))
      .mockResolvedValueOnce(status("finished"));

    const { awaitTask } = inScope();
    const settled = awaitTask("job-1");

    await vi.advanceTimersByTimeAsync(5000);

    await expect(settled).resolves.toBe(true);
    expect(getTaskById).toHaveBeenCalledTimes(2);
  });

  it("stops retrying a persistently failing lookup at the deadline", async () => {
    getTaskById.mockRejectedValue(httpError(503));

    const { awaitTask } = inScope();
    const settled = awaitTask("job-1");

    await vi.advanceTimersByTimeAsync(6 * 60 * 1000);

    await expect(settled).resolves.toBe(true);
  });

  it.each(["failed", "stopped", "canceled"])(
    "stops waiting on a %s job so the caller still refreshes",
    async (terminal) => {
      getTaskById.mockResolvedValue(status(terminal));

      const { awaitTask } = inScope();
      await expect(awaitTask("job-1")).resolves.toBe(true);
    },
  );

  it("tells the caller not to act once the scope is disposed", async () => {
    getTaskById.mockResolvedValue(status("started"));

    const { awaitTask, dispose } = inScope();
    const settled = awaitTask("job-1");
    await vi.advanceTimersByTimeAsync(0);

    dispose();
    await vi.advanceTimersByTimeAsync(5000);

    await expect(settled).resolves.toBe(false);
  });

  it("supersedes an earlier wait when a second one starts", async () => {
    getTaskById.mockResolvedValue(status("started"));

    const { awaitTask } = inScope();
    const first = awaitTask("job-1");
    await vi.advanceTimersByTimeAsync(0);

    getTaskById.mockResolvedValue(status("finished"));
    const second = awaitTask("job-2");

    await expect(first).resolves.toBe(false);
    await expect(second).resolves.toBe(true);
  });

  it("gives up on a job that never reports terminal", async () => {
    getTaskById.mockResolvedValue(status("started"));

    const { awaitTask } = inScope();
    const settled = awaitTask("job-1");

    await vi.advanceTimersByTimeAsync(6 * 60 * 1000);

    await expect(settled).resolves.toBe(true);
  });
});
