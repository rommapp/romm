// `POST /tasks/run/{name}` returns once the job is enqueued, and no socket
// event reports completion, so poll the job's own status.
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
}

export function useTaskCompletion(): UseTaskCompletion {
  let timer: ReturnType<typeof setTimeout> | null = null;
  // The live wait's resolver, doubling as its identity so an in-flight poll
  // knows it was superseded. Cancelling must settle it or the caller hangs.
  let settle: ((observed: boolean) => void) | null = null;

  function cancel() {
    if (timer) clearTimeout(timer);
    timer = null;
    settle?.(false);
    settle = null;
  }

  function awaitTask(taskId: string): Promise<boolean> {
    cancel();
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    let delay = FIRST_POLL_DELAY_MS;

    return new Promise<boolean>((resolve) => {
      settle = resolve;

      const finish = (observed: boolean) => {
        if (settle !== resolve) return;
        settle = null;
        resolve(observed);
      };

      const poll = async () => {
        if (settle !== resolve) return;

        try {
          const { data } = await taskApi.getTaskById(taskId);
          if (settle !== resolve) return;
          if (TERMINAL_STATUSES.includes(data.status)) return finish(true);
        } catch (err) {
          if (settle !== resolve) return;
          // A job past its result TTL 404s, so it ran and is gone. Anything
          // else says nothing about it, so keep polling until the deadline.
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

  return { awaitTask };
}
