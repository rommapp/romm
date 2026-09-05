// useActivityPresence — the "now playing" presence beat a player view sends
// while a game is up, feeding the activity board and the home page's live
// cards. Every player (EmulatorJS, streaming) reports it the same way, so the
// device id, the emit shapes and the timer live here rather than once per view.
//
// Fire-and-forget: presence is cosmetic and must never block or fail a launch.
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";

// The backend expires a presence record a little past this, so a beat slower
// than the expiry would blink the player off the board between ticks.
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
  let timer: ReturnType<typeof setInterval> | null = null;

  function deviceId(): string {
    return auth.user?.current_device_id ?? "web";
  }

  async function beat(): Promise<void> {
    const romId = getRomId();
    if (!auth.user || romId == null) return;
    socket.emit("activity:heartbeat", { rom_id: romId, device_id: deviceId() });
    await onHeartbeat?.();
  }

  function start(): void {
    const romId = getRomId();
    if (!auth.user || romId == null) return;
    if (!socket.connected) socket.connect();
    socket.emit("activity:start", { rom_id: romId, device_id: deviceId() });
    if (!timer) timer = setInterval(() => void beat(), HEARTBEAT_MS);
  }

  function stopHeartbeat(): void {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function emitStop(): void {
    if (!auth.user) return;
    socket.emit("activity:stop", { device_id: deviceId() });
  }

  return { start, stopHeartbeat, emitStop };
}
