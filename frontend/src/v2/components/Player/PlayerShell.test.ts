import { mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import PlayerShell from "./PlayerShell.vue";

const mocks = vi.hoisted(() => ({ setStageActive: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({ setStageActive: mocks.setStageActive }),
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
          name: "RBtn",
          props: ["disabled", "to"],
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
  mocks.setStageActive.mockReset();
});

function backLinks(wrapper: VueWrapper) {
  const [, toRom, toPlatform] = wrapper.findAllComponents({ name: "RBtn" });
  return { toRom: toRom!, toPlatform: toPlatform! };
}

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

  it("links back to the game and to its platform", () => {
    const { toRom, toPlatform } = backLinks(mountShell());

    expect(toRom.props("to")).toEqual({ name: "rom", params: { rom: 1 } });
    expect(toPlatform.props("to")).toEqual({
      name: "platform",
      params: { platform: 2 },
    });
    expect(toPlatform.props("disabled")).toBe(false);
  });

  it("disables the gallery link when the hero carries no platform", () => {
    const { toPlatform } = backLinks(
      mountShell({ heroRom: { id: 1 } as unknown as SimpleRom }),
    );

    expect(toPlatform.props("to")).toBeUndefined();
    expect(toPlatform.props("disabled")).toBe(true);
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

  it("mirrors the running stage into the global chrome flag", async () => {
    const wrapper = mountShell({ running: true });
    expect(mocks.setStageActive).toHaveBeenLastCalledWith(true);

    await wrapper.setProps({ running: false });
    expect(mocks.setStageActive).toHaveBeenLastCalledWith(false);

    await wrapper.setProps({ running: true });
    wrapper.unmount();
    expect(mocks.setStageActive).toHaveBeenLastCalledWith(false);
  });
});
