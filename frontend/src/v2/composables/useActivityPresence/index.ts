// useActivityPresence — the "now playing" beat a player view sends while a
// game is up, feeding the activity board and the home page's live cards.
//
// Fire-and-forget: presence is cosmetic and must never block or fail a launch.
import { useIntervalFn } from "@vueuse/core";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";

// A beat slower than the backend's presence TTL would blink the player off the
// board between ticks.
const HEARTBEAT_MS = 30_000;

export function useActivityPresence(
  getRomId: () => number | null | undefined,
  // Runs on each beat, for a player that has its own liveness to refresh.
  onHeartbeat?: () => void | Promise<void>,
): {
  start: () => void;
  stopHeartbeat: () => void;
  emitStop: () => void;
} {
  const auth = storeAuth();

  function deviceId(): string {
    return auth.user?.current_device_id ?? "web";
  }

  async function beat(): Promise<void> {
    const romId = getRomId();
    if (!auth.user || romId == null) return;
    socket.emit("activity:heartbeat", { rom_id: romId, device_id: deviceId() });
    await onHeartbeat?.();
  }

  // Auto-cleared on scope dispose, so a view unmounting mid-session leaves no
  // timer behind whichever way it left.
  const { pause, resume } = useIntervalFn(beat, HEARTBEAT_MS, {
    immediate: false,
  });

  function start(): void {
    const romId = getRomId();
    if (!auth.user || romId == null) return;
    if (!socket.connected) socket.connect();
    socket.emit("activity:start", { rom_id: romId, device_id: deviceId() });
    resume();
  }

  function emitStop(): void {
    if (!auth.user) return;
    socket.emit("activity:stop", { device_id: deviceId() });
  }

  return { start, stopHeartbeat: pause, emitStop };
}
