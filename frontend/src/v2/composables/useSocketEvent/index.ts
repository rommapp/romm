// useSocketEvent — typed wrapper around the shared Socket.IO instance with
// automatic mount/unmount cleanup.
//
// Replaces the manual pattern:
//   socket.on("scan:done", handler);
//   onBeforeUnmount(() => socket.off("scan:done", handler));
//
// Cleanup uses `onScopeDispose` (not `onBeforeUnmount`) so the composable
// also works correctly when invoked from a non-component effect scope —
// e.g., a Pinia store action that subscribes to a socket event for the
// store's lifetime, or a manually-scoped subscription via
// `effectScope().run(...)`.
//
// Auto-connect: by default, ensures the singleton socket is connected
// before subscribing. Pass `{ connect: false }` to opt out — useful when a
// caller knows the socket lifecycle is managed elsewhere.
//
// Typing: the payload is generic. Until the backend ships a typed event
// map (constitution §X.10 — backend debt), event names are plain strings
// and the consumer asserts the payload shape. When the typed catalogue
// lands, we re-export an overload keyed on the event-map and the cast
// inside disappears.
import { onScopeDispose } from "vue";
import socket from "@/services/socket";

interface Options {
  /** Connect the socket if it isn't already (default true). */
  connect?: boolean;
}

export interface SocketEventHandle {
  /** Unsubscribe early. Idempotent — subsequent calls are no-ops. The
   * scope's automatic cleanup will also call this if it hasn't fired. */
  stop: () => void;
}

export function useSocketEvent<T = unknown>(
  event: string,
  handler: (payload: T) => void,
  options: Options = {},
): SocketEventHandle {
  if (options.connect !== false && !socket.connected) socket.connect();

  // socket.io-client's `on` is overloaded; cast to the broad signature so
  // the generic-typed `handler` lines up with the runtime contract
  // (Socket.IO passes whatever the emitter sent).
  const wrapped = handler as unknown as (...args: unknown[]) => void;
  socket.on(event, wrapped);

  let stopped = false;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    socket.off(event, wrapped);
  };

  onScopeDispose(stop);

  return { stop };
}
