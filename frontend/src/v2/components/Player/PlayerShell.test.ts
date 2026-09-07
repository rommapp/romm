import { mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import PlayerShell from "./PlayerShell.vue";

const mocks = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

vi.mock("@/v2/components/shared/GameCover.vue", () => ({
  default: { template: "<div class='game-cover' />" },
}));

const heroRom = { id: 1, platform_id: 2 } as unknown as SimpleRom;

function mountShell(
  props: Partial<{
    heroRom: SimpleRom | null;
    ready: boolean;
    running: boolean;
    quitting: boolean;
  }> = {},
): VueWrapper {
  return mount(PlayerShell, {
    props: {
      heroRom,
      title: "Game",
      platformLabel: "Platform",
      romId: 1,
      ready: true,
      running: false,
      ...props,
    },
    slots: { stage: "<div class='stage' />" },
    global: {
      stubs: {
        RBtn: {
          props: ["disabled"],
          emits: ["click"],
          template:
            '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
        RCard: { template: "<div><slot /></div>" },
        RSpinner: true,
      },
    },
  });
}

beforeEach(() => {
  mocks.push.mockReset();
});

describe("PlayerShell", () => {
  it("waits on a spinner until a hero is available", () => {
    const wrapper = mountShell({ heroRom: null });

    expect(wrapper.findComponent({ name: "RSpinner" }).exists()).toBe(true);
    expect(wrapper.find(".r-v2-player__play").exists()).toBe(false);
  });

  it("blocks play until the full payload has landed", async () => {
    const wrapper = mountShell({ ready: false });

    const play = wrapper.get(".r-v2-player__play");
    expect(play.attributes("disabled")).toBeDefined();

    await play.trigger("click");
    expect(wrapper.emitted("play")).toBeUndefined();
  });

  it("emits play once the payload is ready", async () => {
    const wrapper = mountShell();

    await wrapper.get(".r-v2-player__play").trigger("click");

    expect(wrapper.emitted("play")).toHaveLength(1);
  });

  it("navigates back to the game and to its platform", async () => {
    const wrapper = mountShell();

    const buttons = wrapper.findAll("button");
    await buttons[1]!.trigger("click");
    await buttons[2]!.trigger("click");

    expect(mocks.push).toHaveBeenNthCalledWith(1, {
      name: "rom",
      params: { rom: 1 },
    });
    expect(mocks.push).toHaveBeenNthCalledWith(2, {
      name: "platform",
      params: { platform: 2 },
    });
  });

  it("skips the gallery link when the hero carries no platform", async () => {
    const wrapper = mountShell({
      heroRom: { id: 1 } as unknown as SimpleRom,
    });

    await wrapper.findAll("button")[2]!.trigger("click");

    expect(mocks.push).not.toHaveBeenCalledWith(
      expect.objectContaining({ name: "platform" }),
    );
  });

  it("swaps the config panel for the stage while running", async () => {
    const wrapper = mountShell({ running: true });

    expect(wrapper.find(".stage").exists()).toBe(true);
    expect(wrapper.find(".r-v2-player__play").exists()).toBe(false);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    expect(wrapper.emitted("quit")).toHaveLength(1);
  });

  it("keeps the quit button busy while an exit is still saving", () => {
    const wrapper = mountShell({ running: true, quitting: true });

    expect(
      wrapper.get(".r-v2-player__quit").attributes("disabled"),
    ).toBeDefined();
  });
});
