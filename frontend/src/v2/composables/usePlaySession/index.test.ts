import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import playSessionApi from "@/services/api/play-session";
import type { SimpleRom } from "@/stores/roms";
import { usePlaySession } from "./index";

vi.mock("@/services/api/play-session", () => ({
  default: { ingestPlaySessionsKeepalive: vi.fn() },
}));

// Controllable auth stand-in: tests tweak scopes / user between cases.
const authState = {
  scopes: ["roms.user.write"] as string[],
  user: { current_device_id: "device-1" } as {
    current_device_id: string;
  } | null,
};
vi.mock("@/stores/auth", () => ({
  default: () => authState,
}));

const ingest = vi.mocked(playSessionApi.ingestPlaySessionsKeepalive);

function makeRom(id = 7): SimpleRom {
  return { id } as unknown as SimpleRom;
}

beforeEach(() => {
  ingest.mockReset();
  authState.scopes = ["roms.user.write"];
  authState.user = { current_device_id: "device-1" };
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-07-21T10:00:00.000Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("usePlaySession", () => {
  it("ingests a session with real start/end/duration on flush", () => {
    const { start, flush } = usePlaySession();
    start(makeRom(42));
    vi.advanceTimersByTime(90_000);
    flush();

    expect(ingest).toHaveBeenCalledTimes(1);
    expect(ingest).toHaveBeenCalledWith({
      deviceId: "device-1",
      sessions: [
        {
          rom_id: 42,
          start_time: "2026-07-21T10:00:00.000Z",
          end_time: "2026-07-21T10:01:30.000Z",
          duration_ms: 90_000,
        },
      ],
    });
  });

  it("does nothing without a write scope", () => {
    authState.scopes = ["roms.user.read"];
    const { start, flush } = usePlaySession();
    start(makeRom());
    vi.advanceTimersByTime(90_000);
    flush();
    expect(ingest).not.toHaveBeenCalled();
  });

  it("drops sub-second sessions", () => {
    const { start, flush } = usePlaySession();
    start(makeRom());
    vi.advanceTimersByTime(500);
    flush();
    expect(ingest).not.toHaveBeenCalled();
  });

  it("is idempotent — a second flush does not resubmit", () => {
    const { start, flush } = usePlaySession();
    start(makeRom());
    vi.advanceTimersByTime(90_000);
    flush();
    flush();
    expect(ingest).toHaveBeenCalledTimes(1);
  });

  it("flush without a prior start is a no-op", () => {
    const { flush } = usePlaySession();
    flush();
    expect(ingest).not.toHaveBeenCalled();
  });

  it("sends a null device id when the user has none", () => {
    authState.user = null;
    const { start, flush } = usePlaySession();
    start(makeRom());
    vi.advanceTimersByTime(90_000);
    flush();
    expect(ingest).toHaveBeenCalledWith(
      expect.objectContaining({ deviceId: null }),
    );
  });
});
