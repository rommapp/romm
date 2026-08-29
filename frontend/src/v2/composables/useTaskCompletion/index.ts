// `POST /tasks/run/{name}` returns as soon as the job is enqueued, so a caller
// that wants to show the job's effect has to wait for the worker. There is no
// socket event for task completion, so poll the job's own status.
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
  // The live wait's resolver, which doubles as its identity: a poll still in
  // flight compares against it to know whether it was superseded. Cancelling
  // clears the pending timer, so it has to settle the outstanding promise
  // itself or the caller waits on it forever.
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

  return { awaitTask };
}
