import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeTasks from "@/stores/tasks";
import type { TaskStatusResponse } from "@/utils/tasks";
import { taskStatusFixture } from "@/utils/tasks.fixtures";

const { getTaskStatus } = vi.hoisted(() => ({ getTaskStatus: vi.fn() }));

vi.mock("@/services/api/task", () => ({ default: { getTaskStatus } }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

const OLD: TaskStatusResponse[] = [taskStatusFixture({ task_id: "old" })];
const NEW: TaskStatusResponse[] = [taskStatusFixture({ task_id: "new" })];

describe("tasks store fetchTaskStatus", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("keeps the newest response when an older one settles last", async () => {
    const older = deferred<{ data: TaskStatusResponse[] }>();
    const newer = deferred<{ data: TaskStatusResponse[] }>();
    getTaskStatus
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise);
    const store = storeTasks();

    const first = store.fetchTaskStatus();
    const second = store.fetchTaskStatus();
    newer.resolve({ data: NEW });
    await second;
    older.resolve({ data: OLD });
    await first;

    expect(store.taskStatuses).toEqual(NEW);
  });

  it("ignores a failure from a superseded request", async () => {
    const older = deferred<{ data: TaskStatusResponse[] }>();
    getTaskStatus
      .mockReturnValueOnce(
        older.promise.then(() => Promise.reject(new Error("x"))),
      )
      .mockResolvedValueOnce({ data: NEW });
    vi.spyOn(console, "error").mockImplementation(() => {});
    const store = storeTasks();

    const first = store.fetchTaskStatus();
    await store.fetchTaskStatus();
    older.resolve({ data: OLD });
    await first;

    expect(store.taskStatuses).toEqual(NEW);
  });

  it("applies an older success that settles after a newer failure", async () => {
    const older = deferred<{ data: TaskStatusResponse[] }>();
    getTaskStatus
      .mockReturnValueOnce(older.promise)
      .mockRejectedValueOnce(new Error("x"));
    vi.spyOn(console, "error").mockImplementation(() => {});
    const store = storeTasks();

    const first = store.fetchTaskStatus();
    await store.fetchTaskStatus();
    older.resolve({ data: OLD });
    await first;

    expect(store.taskStatuses).toEqual(OLD);
  });
});
