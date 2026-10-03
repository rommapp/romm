import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EasyRpg from "./EasyRpg.vue";

const mocks = vi.hoisted(() => ({
  flushPlaySession: vi.fn(),
  getRom: vi.fn(),
  playSessionStart: vi.fn(),
  routerReplace: vi.fn(() => Promise.resolve()),
  setPlaying: vi.fn(),
  setStageActive: vi.fn(),
}));

vi.mock("vue-i18n");

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: vi.fn(),
  useRoute: () => ({ params: { rom: "1" } }),
  useRouter: () => ({ replace: mocks.routerReplace }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom: mocks.getRom },
}));

vi.mock("@/stores/auth", () => ({
  default: () => ({ user: { id: 7 } }),
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({
    setPlaying: mocks.setPlaying,
    setStageActive: mocks.setStageActive,
  }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ getDetailedRom: () => null }),
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
  name: "Yume Nikki",
  fs_name_no_ext: "Yume Nikki",
  platform_id: 2,
  platform_slug: "rpg-maker",
  rom_user: { status: null },
};

beforeEach(() => {
  mocks.getRom.mockResolvedValue({ data: rom });
});

function mountView(): VueWrapper {
  return mount(EasyRpg, {
    global: {
      stubs: {
        RBtn: {
          name: "RBtn",
          props: { to: { type: String, default: undefined } },
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RCard: { template: "<div><slot /></div>" },
        RSpinner: true,
        RSwitch: true,
      },
    },
  });
}

async function play(): Promise<VueWrapper> {
  const wrapper = mountView();
  await flushPromises();
  await wrapper.get(".r-v2-player__play").trigger("click");
  await flushPromises();
  return wrapper;
}

describe("EasyRpg", () => {
  it("boots the game under a save name scoped to the user", async () => {
    const wrapper = await play();

    expect(wrapper.get("iframe").attributes("src")).toBe(
      "/assets/easyrpg/index.html?game=1-7",
    );
    wrapper.unmount();
  });

  it("starts timing the session once the player page loads", async () => {
    const wrapper = await play();
    expect(mocks.playSessionStart).not.toHaveBeenCalled();

    await wrapper.get("iframe").trigger("load");
    await wrapper.get("iframe").trigger("load");

    expect(mocks.playSessionStart).toHaveBeenCalledTimes(1);
    expect(mocks.playSessionStart).toHaveBeenCalledWith(rom);
    wrapper.unmount();
  });

  it("records the play session and returns to the game on quit", async () => {
    const wrapper = await play();

    await wrapper.get(".r-v2-player__quit").trigger("click");

    expect(mocks.flushPlaySession).toHaveBeenCalled();
    expect(mocks.routerReplace).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });

  it("records the play session when the page goes away", async () => {
    const wrapper = await play();

    window.dispatchEvent(new Event("pagehide"));

    expect(mocks.flushPlaySession).toHaveBeenCalled();
    wrapper.unmount();
  });
});
