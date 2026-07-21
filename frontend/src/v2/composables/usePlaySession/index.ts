// usePlaySession — records a single play session's wall-clock and ingests it
// on flush. The session is what drives the server-side rom_user update
// (last_played + now_playing + status), replacing the old optimistic
// launch-time write.
//
// Fire-and-forget: entering or leaving gameplay must never block on the
// network. flush() is idempotent, so the several exit paths a player has
// (stop button, save-and-exit, back navigation, unmount) can each call it
// without risking a double submission.
import playSessionApi from "@/services/api/play-session";
import storeAuth from "@/stores/auth";
import type { SimpleRom } from "@/stores/roms";

// Sessions shorter than a second carry no meaningful playtime and would be
// rejected anyway: the backend floors timestamps to whole seconds and
// requires end_time > start_time. A tap-Play-then-quit is dropped.
const MIN_SESSION_MS = 1000;

export function usePlaySession(): {
  start: (rom: SimpleRom) => void;
  flush: () => void;
} {
  const auth = storeAuth();
  let startTime: Date | null = null;
  let romId: number | null = null;

  function start(rom: SimpleRom): void {
    // Recording is gated on the same scope the ingest endpoint requires.
    if (!auth.scopes.includes("roms.user.write")) return;
    startTime = new Date();
    romId = rom.id;
  }

  function flush(): void {
    if (startTime === null || romId === null) return;
    const sessionStart = startTime;
    const sessionRomId = romId;
    // Clear before the async call so a second flush is a no-op.
    startTime = null;
    romId = null;

    const endTime = new Date();
    const durationMs = endTime.getTime() - sessionStart.getTime();
    if (durationMs < MIN_SESSION_MS) return;

    playSessionApi.ingestPlaySessionsKeepalive({
      deviceId: auth.user?.current_device_id ?? null,
      sessions: [
        {
          rom_id: sessionRomId,
          start_time: sessionStart.toISOString(),
          end_time: endTime.toISOString(),
          duration_ms: durationMs,
        },
      ],
    });
  }

  return { start, flush };
}
