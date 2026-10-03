import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
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

function mountPlayer() {
  const wrapper = mount(MiniPlayer, {
    global: { stubs: { NowPlayingCard: true } },
  });
  const audio = wrapper.get("audio").element;
  return { wrapper, audio, store: useSoundtrackPlayer() };
}

describe("MiniPlayer buffering", () => {
  beforeEach(() =>
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }),
  );

  it("reports buffering only once a wait outlasts a second", () => {
    const { audio, store } = mountPlayer();

    audio.dispatchEvent(new Event("waiting"));
    vi.advanceTimersByTime(999);
    expect(store.isBuffering).toBe(false);

    vi.advanceTimersByTime(1);
    expect(store.isBuffering).toBe(true);

    audio.dispatchEvent(new Event("canplay"));
    expect(store.isBuffering).toBe(false);
  });

  it("never reports a wait that resolves in time", () => {
    const { audio, store } = mountPlayer();

    audio.dispatchEvent(new Event("waiting"));
    vi.advanceTimersByTime(500);
    audio.dispatchEvent(new Event("canplay"));
    vi.advanceTimersByTime(1000);

    expect(store.isBuffering).toBe(false);
  });

  it("drops a pending report on unmount", () => {
    const { wrapper, audio, store } = mountPlayer();

    audio.dispatchEvent(new Event("waiting"));
    wrapper.unmount();
    vi.advanceTimersByTime(1000);

    expect(store.isBuffering).toBe(false);
  });
});
