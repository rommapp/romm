import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import MiniPlayer from "./MiniPlayer.vue";

vi.mock("vue-i18n");

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(false) }),
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
    const { play } = await mountRestored(true);
    expect(play).not.toHaveBeenCalled();

    window.dispatchEvent(new Event("keydown"));
    window.dispatchEvent(new Event("keydown"));

    expect(play).toHaveBeenCalledTimes(1);
  });

  it("waits for a play press when the session was paused", async () => {
    const { play } = await mountRestored(false);

    window.dispatchEvent(new Event("pointerdown"));

    expect(play).not.toHaveBeenCalled();
  });

  it("drops a restored track that fails to load without a toast", async () => {
    const { audio, store } = await mountRestored(true);

    audio.dispatchEvent(new Event("error"));

    expect(store.track).toBeNull();
  });
});
