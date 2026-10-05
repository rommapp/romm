import type { CleanupTaskStatusResponse } from "@/__generated__/models/CleanupTaskStatusResponse";

export function taskStatusFixture(
  overrides: Partial<CleanupTaskStatusResponse> = {},
): CleanupTaskStatusResponse {
  return {
    task_key: null,
    task_name: "Scheduled ZIP cache cleanup",
    task_id: "job-1",
    task_type: "cleanup",
    status: "started",
    created_at: null,
    enqueued_at: null,
    started_at: null,
    ended_at: null,
    meta: { cleanup_stats: null },
    ...overrides,
  };
}
