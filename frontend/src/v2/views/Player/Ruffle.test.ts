import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { nextTick } from "vue";
import type { RuffleSourceAPI } from "@/types/ruffle";
import Ruffle from "./Ruffle.vue";

const mocks = vi.hoisted(() => ({
  getRom: vi.fn(),
  playSessionStart: vi.fn(),
  flushPlaySession: vi.fn(),
  push: vi.fn(),
  setPlaying: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { rom: "1" } }),
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom: mocks.getRom },
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({ setPlaying: mocks.setPlaying }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ currentRom: null }),
}));

vi.mock("@/utils", () => ({
  getDownloadPath: () => "/api/roms/1/content/game.swf",
}));

vi.mock("@/v2/components/shared/GameCover.vue", () => ({
  default: { template: "<div />" },
}));

vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));

vi.mock("@/v2/composables/useFullscreenPref", async () => {
  const { ref } = await import("vue");
  return { useFullscreenPref: () => ({ fullscreenOnPlay: ref(false) }) };
});

vi.mock("@/v2/composables/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("@/v2/composables/usePlaySession", () => ({
  usePlaySession: () => ({
    start: mocks.playSessionStart,
    flush: mocks.flushPlaySession,
  }),
}));

vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => ({ getRomById: () => null }),
}));

const rom = {
  id: 1,
  name: "Flash Game",
  fs_name_no_ext: "Flash Game",
  platform_id: 2,
  platform_slug: "flash",
  rom_user: { status: null },
};

// Swallow the Ruffle runtime <script> injections; the test drives
// window.RufflePlayer directly.
beforeAll(() => {
  const appendChild = document.body.appendChild.bind(document.body);
  vi.spyOn(document.body, "appendChild").mockImplementation((node) =>
    (node as Element).tagName === "SCRIPT" ? node : appendChild(node),
  );
});

afterAll(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getRom.mockResolvedValue({ data: rom });
  window.RufflePlayer = {
    newest: () => null,
  } as unknown as typeof window.RufflePlayer;
});

function makeRuffleSource(): RuffleSourceAPI {
  const player = Object.assign(document.createElement("div"), {
    load: vi.fn(),
    fullscreenEnabled: false,
    enterFullscreen: vi.fn(),
  });
  return {
    createPlayer: () => player,
  } as unknown as RuffleSourceAPI;
}

async function mountAndPlay(): Promise<VueWrapper> {
  const wrapper = mount(Ruffle, {
    attachTo: document.body,
    global: {
      stubs: {
        RBtn: {
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RCard: { template: "<div><slot /></div>" },
        RIcon: true,
        RSpinner: true,
        RSwitch: true,
      },
    },
  });
  await flushPromises();
  await wrapper.get(".r-v2-player__play").trigger("click");
  await nextTick();
  return wrapper;
}

function dispatchUnload(): Event {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event;
}

describe("Ruffle launch", () => {
  it("guards the unload once a player is running", async () => {
    window.RufflePlayer = {
      newest: () => makeRuffleSource(),
    } as unknown as typeof window.RufflePlayer;

    const wrapper = await mountAndPlay();

    expect(mocks.playSessionStart).toHaveBeenCalledOnce();
    expect(dispatchUnload().defaultPrevented).toBe(true);
    wrapper.unmount();
  });

  // A failed launch used to leave the running state set, so the browser asked
  // for a leave confirmation with no game behind it.
  it("clears the running state when no Ruffle source is available", async () => {
    const wrapper = await mountAndPlay();

    expect(mocks.playSessionStart).not.toHaveBeenCalled();
    expect(mocks.setPlaying).toHaveBeenLastCalledWith(false);
    expect(dispatchUnload().defaultPrevented).toBe(false);
    wrapper.unmount();
  });
});
