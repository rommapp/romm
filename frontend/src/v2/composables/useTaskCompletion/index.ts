// useTaskCompletion — wait for a queued RQ job to finish before reacting to it.
//
// `POST /tasks/run/{name}` returns as soon as the job is enqueued, so anything
// that wants to show the job's effect has to wait for the worker. Guessing at
// a fixed delay loses the race whenever the worker is busy or the job is slow,
// which leaves the caller showing stale data behind a success toast. Polling
// the job's own status instead means the wait is as long as the job actually
// takes. There is no socket event for task completion, and `TasksSection`
// already polls task status, so this follows the same mechanism scoped to one
// job.
//
// Usage:
//   const { awaitTask } = useTaskCompletion();
//   const { data } = await taskApi.runTask("cleanup_missing_roms", body);
//   if (await awaitTask(data.task_id)) await refresh();
import axios from "axios";
import { onScopeDispose } from "vue";
import type { JobStatus } from "@/__generated__";
import taskApi from "@/services/api/task";

const TERMINAL_STATUSES: readonly JobStatus[] = [
  "finished",
  "failed",
  "stopped",
  "canceled",
];

const FIRST_POLL_DELAY_MS = 400;
const POLL_BACKOFF = 1.5;
const MAX_POLL_DELAY_MS = 5000;
// Cleanups on a large library run for a while; stop waiting well after that
// rather than polling forever behind a tab nobody is looking at.
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export interface UseTaskCompletion {
  /**
   * Polls `task_id` until it reaches a terminal state. Resolves true when the
   * caller should act on the result, false when the wait was cancelled (the
   * component went away, or another task superseded this one).
   *
   * Resolves true on timeout and on a job that can no longer be fetched, so a
   * refresh still happens on a best-effort basis.
   */
  awaitTask: (taskId: string) => Promise<boolean>;
  /** Abandons an in-flight wait. Called automatically on scope dispose. */
  cancel: () => void;
}

export function useTaskCompletion(): UseTaskCompletion {
  let timer: ReturnType<typeof setTimeout> | null = null;
  // Bumped on cancel so a poll already in flight knows it was superseded.
  let generation = 0;
  // Cancelling clears the pending timer, so it has to settle the outstanding
  // promise itself or the caller waits on it forever.
  let settle: ((observed: boolean) => void) | null = null;

  function cancel() {
    generation += 1;
    if (timer) clearTimeout(timer);
    timer = null;
    settle?.(false);
    settle = null;
  }

  function awaitTask(taskId: string): Promise<boolean> {
    cancel();
    const mine = generation;
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    let delay = FIRST_POLL_DELAY_MS;

    return new Promise<boolean>((resolve) => {
      settle = resolve;

      const finish = (observed: boolean) => {
        if (mine !== generation) return;
        settle = null;
        resolve(observed);
      };

      const poll = async () => {
        if (mine !== generation) return;

        try {
          const { data } = await taskApi.getTaskById(taskId);
          if (mine !== generation) return;
          if (TERMINAL_STATUSES.includes(data.status)) return finish(true);
        } catch (err) {
          if (mine !== generation) return;
          // A job past its result TTL 404s, which means it ran and is gone.
          // Anything else (a timeout, a 5xx) says nothing about the job, so
          // keep polling rather than refreshing over a cleanup still in
          // progress. The deadline below still bounds the wait.
          if (axios.isAxiosError(err) && err.response?.status === 404) {
            return finish(true);
          }
        }

        if (Date.now() >= deadline) return finish(true);

        timer = setTimeout(() => void poll(), delay);
        delay = Math.min(delay * POLL_BACKOFF, MAX_POLL_DELAY_MS);
      };

      void poll();
    });
  }

  onScopeDispose(cancel);

  return { awaitTask, cancel };
}
