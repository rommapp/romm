// useServerConnection — single orchestrator for backend reachability in v2.
//
// Three signals keep `heartbeat.connected` (the shared source of truth) fresh:
//   * Passive — the axios interceptor dispatches `backend-online` /
//     `backend-offline` / `backend-suspect` DOM events on every response; we
//     mirror them onto the store so the offline notice reacts the instant a
//     request fails.
//   * Active — a self-rescheduling `/heartbeat` poll (short per-call timeout,
//     not the global 120s) detects breakage while idle and, crucially,
//     reconnection. Polls faster while offline.
//   * Recovery — on a false→true transition we do a full page refresh. A fresh
//     boot re-runs initializeData() + the router guard from scratch, so the
//     user lands on the correct destination (setup / login / home) with clean
//     state instead of a half-recovered SPA.
//
// `install()` runs once for the app's lifetime (idempotent). The banner calls
// `useServerConnection()` in its <script setup>, which both returns the
// reactive `isOffline` flag and triggers the install.
import { debounce } from "lodash";
import { computed, effectScope, watch } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

// While online, probe only occasionally — a network blip shouldn't rush to
// flag the backend as down. Passive interceptor events still flip us offline
// the instant a real request fails, so this slow poll is just a safety net.
const POLL_ONLINE_MS = 5 * 60_000;
// Once offline, poll quickly so recovery is picked up promptly.
const POLL_OFFLINE_MS = 5_000;
const HEARTBEAT_TIMEOUT_MS = 5_000;

let installed = false;

/** A full refresh fires only on a real reconnect: offline (false) → online. */
export function shouldRefreshOnReconnect(
  now: boolean,
  was: boolean | undefined,
): boolean {
  return now && was === false;
}

function install() {
  const heartbeat = storeHeartbeat();

  // Passive detection — the interceptor classifies each response:
  //   * backend-online  → a request succeeded; the backend is up.
  //   * backend-offline → a network-level failure (no response); down.
  //   * backend-suspect → a 5xx from some endpoint; confirm authoritatively
  //     via the /heartbeat probe rather than trusting a single failure. The
  //     probe's own result (5xx/network → offline) drives `connected`.
  document.addEventListener("backend-online", () =>
    heartbeat.setConnected(true),
  );
  document.addEventListener("backend-offline", () =>
    heartbeat.setConnected(false),
  );
  const confirmHealth = debounce(() => {
    void heartbeat.fetchHeartbeat({ timeout: HEARTBEAT_TIMEOUT_MS });
  }, 300);
  document.addEventListener("backend-suspect", () => confirmHealth());

  // Recovery — refresh the page on a real reconnect. Run in a detached effect
  // scope so the watcher lives for the app's lifetime rather than the banner's
  // (the banner unmounts on a live v1↔v2 UI switch, yet `install()` only ever
  // runs once, so a scope-bound watcher would silently die on the way back).
  effectScope(true).run(() => {
    watch(
      () => heartbeat.connected,
      (now, was) => {
        if (shouldRefreshOnReconnect(now, was)) window.location.reload();
      },
    );
  });

  // Active poll — self-reschedules, faster while offline for snappy recovery.
  function scheduleNext() {
    const delay = heartbeat.connected ? POLL_ONLINE_MS : POLL_OFFLINE_MS;
    setTimeout(async () => {
      await heartbeat.fetchHeartbeat({ timeout: HEARTBEAT_TIMEOUT_MS });
      scheduleNext();
    }, delay);
  }
  scheduleNext();
}

export function useServerConnection() {
  const heartbeat = storeHeartbeat();

  if (!installed) {
    installed = true;
    install();
  }

  const isOffline = computed(() => !heartbeat.connected);

  /** Force an immediate reachability re-check (e.g. the notice's Retry). */
  function retryNow() {
    return heartbeat.fetchHeartbeat({ timeout: HEARTBEAT_TIMEOUT_MS });
  }

  return { isOffline, retryNow };
}
