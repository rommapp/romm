import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import storePlaying from "@/stores/playing";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import MiniPlayer from "./MiniPlayer.vue";

vi.mock("vue-i18n");

const smAndDown = await vi.hoisted(async () => {
  const { ref } = await import("vue");
  return ref(false);
});
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown }),
}));

vi.mock("@/v2/composables/useMediaSession", () => ({
  useMediaSession: vi.fn(),
}));

vi.mock("@/v2/composables/useMiniPlayerVisible", () => ({
  useMiniPlayerVisible: () => ref(false),
}));

vi.mock("@/v2/composables/useSoundtrackResume", () => ({
  useSoundtrackResume: vi.fn(),
}));

async function mountPlayer() {
  const wrapper = mount(MiniPlayer, {
    global: { stubs: { NowPlayingCard: true } },
  });
  // The player's event listeners attach once the first render has flushed.
  await nextTick();
  const audio = wrapper.get("audio").element;
  return { wrapper, audio, store: useSoundtrackPlayer() };
}

describe("MiniPlayer buffering", () => {
  beforeEach(() =>
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }),
  );

  it("reports buffering only once a wait outlasts a second", async () => {
    const { audio, store } = await mountPlayer();

    audio.dispatchEvent(new Event("waiting"));
    vi.advanceTimersByTime(999);
    expect(store.isBuffering).toBe(false);

    vi.advanceTimersByTime(1);
    expect(store.isBuffering).toBe(true);

    audio.dispatchEvent(new Event("canplay"));
    expect(store.isBuffering).toBe(false);
  });

  it("never reports a wait that resolves in time", async () => {
    const { audio, store } = await mountPlayer();

    audio.dispatchEvent(new Event("waiting"));
    vi.advanceTimersByTime(500);
    audio.dispatchEvent(new Event("canplay"));
    vi.advanceTimersByTime(1000);

    expect(store.isBuffering).toBe(false);
  });

  it("drops a pending report on unmount", async () => {
    const { wrapper, audio, store } = await mountPlayer();

    audio.dispatchEvent(new Event("waiting"));
    wrapper.unmount();
    vi.advanceTimersByTime(1000);

    expect(store.isBuffering).toBe(false);
  });
});

describe("MiniPlayer track changes", () => {
  it("stops reporting playback when the next track's start is refused", async () => {
    const { audio, store } = await mountPlayer();
    vi.spyOn(audio, "play").mockRejectedValue(new Error("NotAllowedError"));
    vi.spyOn(audio, "load").mockImplementation(() => {});
    store.setPlaying(true);

    store.play(
      { romId: 1, fileId: 2, fileName: "02 Theme.mp3", url: "/theme.mp3" },
      {},
    );
    await flushPromises();

    expect(store.isPlaying).toBe(false);
  });
});

describe("MiniPlayer restored session", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    smAndDown.value = false;
  });

  const track = {
    romId: 1,
    fileId: 2,
    fileName: "02 Theme.mp3",
    url: "/theme.mp3",
  };

  function restore(
    store: ReturnType<typeof useSoundtrackPlayer>,
    wasPlaying: boolean,
  ) {
    store.restore({
      track,
      meta: {},
      playlist: [track],
      originalPlaylist: [track],
      isShuffled: false,
      playlistMeta: {},
      activePlaylistRomId: null,
      position: 42,
      wasPlaying,
    });
  }

  async function mountRestored(wasPlaying: boolean) {
    const mounted = await mountPlayer();
    const play = vi.spyOn(mounted.audio, "play").mockResolvedValue();
    vi.spyOn(mounted.audio, "load").mockImplementation(() => {});
    restore(mounted.store, wasPlaying);
    await flushPromises();
    return { ...mounted, play };
  }

  it("loads paused and seeks to the saved position", async () => {
    const { audio, play } = await mountRestored(false);

    audio.dispatchEvent(new Event("loadedmetadata"));

    expect(play).not.toHaveBeenCalled();
    expect(audio.currentTime).toBe(42);
  });

  it("starts a session that was playing on the first interaction", async () => {
    const { audio, play } = await mountRestored(true);
    let playing = false;
    Object.defineProperty(audio, "paused", { get: () => !playing });
    play.mockImplementation(async () => {
      playing = true;
    });
    expect(play).not.toHaveBeenCalled();

    window.dispatchEvent(new Event("keyup"));
    window.dispatchEvent(new Event("keyup"));
    vi.advanceTimersByTime(0);

    expect(play).toHaveBeenCalledTimes(1);
  });

  it("leaves a first press on Play playing", async () => {
    const { audio, store, play } = await mountRestored(true);
    let playing = false;
    Object.defineProperty(audio, "paused", { get: () => !playing });
    play.mockImplementation(async () => {
      playing = true;
    });
    const pause = vi.spyOn(audio, "pause").mockImplementation(() => {
      playing = false;
    });
    const button = document.body.appendChild(document.createElement("button"));
    button.addEventListener("click", () => store.togglePlayPause());

    button.click();
    vi.advanceTimersByTime(0);

    expect(play).toHaveBeenCalledTimes(1);
    expect(pause).not.toHaveBeenCalled();
    button.remove();
  });

  it("keeps waiting while a game blocks the music", async () => {
    const { play } = await mountRestored(true);
    smAndDown.value = true;
    storePlaying().setStageActive(true);

    window.dispatchEvent(new Event("click"));
    vi.advanceTimersByTime(0);
    expect(play).not.toHaveBeenCalled();

    storePlaying().setStageActive(false);
    window.dispatchEvent(new Event("click"));
    vi.advanceTimersByTime(0);
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("keeps waiting when the press itself starts a game", async () => {
    const { play } = await mountRestored(true);
    smAndDown.value = true;
    const button = document.body.appendChild(document.createElement("button"));
    button.addEventListener("click", () => storePlaying().setStageActive(true));

    button.click();
    vi.advanceTimersByTime(0);
    expect(play).not.toHaveBeenCalled();

    storePlaying().setStageActive(false);
    window.dispatchEvent(new Event("click"));
    vi.advanceTimersByTime(0);
    expect(play).toHaveBeenCalledTimes(1);
    button.remove();
  });

  it("tries again on the next press when the start is refused", async () => {
    const { play } = await mountRestored(true);
    play.mockRejectedValueOnce(new Error("NotAllowedError"));

    window.dispatchEvent(new Event("keyup"));
    vi.advanceTimersByTime(0);
    await flushPromises();
    window.dispatchEvent(new Event("keyup"));
    vi.advanceTimersByTime(0);

    expect(play).toHaveBeenCalledTimes(2);
  });

  it("stops waiting once playback starts another way", async () => {
    const { audio, play } = await mountRestored(true);

    audio.dispatchEvent(new Event("play"));
    window.dispatchEvent(new Event("click"));
    vi.advanceTimersByTime(0);

    expect(play).not.toHaveBeenCalled();
  });

  it("waits for a play press when the session was paused", async () => {
    const { play } = await mountRestored(false);

    window.dispatchEvent(new Event("click"));
    vi.advanceTimersByTime(0);

    expect(play).not.toHaveBeenCalled();
  });

  it("drops a restored track that fails to load without a toast", async () => {
    const { audio, store } = await mountRestored(true);

    audio.dispatchEvent(new Event("error"));

    expect(store.track).toBeNull();
  });
});
