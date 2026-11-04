import { beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import { usePlaybackTime } from "./index";

describe("usePlaybackTime", () => {
  let frame: FrameRequestCallback | null = null;

  // Runs the pending frame at `now`; the loop re-arms itself.
  function step(now: number) {
    const pending = frame;
    frame = null;
    pending?.(now);
  }

  beforeEach(() => {
    frame = null;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frame = cb;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frame = null;
    });
    vi.spyOn(performance, "now").mockReturnValue(1000);
  });

  function setup() {
    const scope = effectScope();
    const time = scope.run(() => usePlaybackTime())!;
    return { scope, time };
  }

  it("advances between the audio's reports while playing", async () => {
    const player = useSoundtrackPlayer();
    player.currentTime = 10;
    player.duration = 60;
    const { time } = setup();

    player.isPlaying = true;
    await nextTick();
    step(1500);

    expect(time.value).toBe(10.5);
  });

  it("stops at the end of the track", async () => {
    const player = useSoundtrackPlayer();
    player.currentTime = 59;
    player.duration = 60;
    const { time } = setup();

    player.isPlaying = true;
    await nextTick();
    step(5000);

    expect(time.value).toBe(60);
  });

  it("holds still while paused or buffering", async () => {
    const player = useSoundtrackPlayer();
    player.isPlaying = true;
    setup();
    await nextTick();
    expect(frame).not.toBeNull();

    player.isBuffering = true;
    await nextTick();
    expect(frame).toBeNull();

    player.isBuffering = false;
    player.isPlaying = false;
    await nextTick();
    expect(frame).toBeNull();
  });

  it("stops ticking once its scope is disposed", async () => {
    const player = useSoundtrackPlayer();
    player.isPlaying = true;
    const { scope } = setup();
    await nextTick();

    scope.stop();

    expect(frame).toBeNull();
  });
});
