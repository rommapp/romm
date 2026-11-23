import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import { romFixture } from "@/utils/rom.fixtures";
import PlayButton from "./PlayButton.vue";

const rom = romFixture({
  id: 42,
  name: "Luigi's Mansion",
  platform_slug: "ngc",
});

const play = vi.hoisted(() => vi.fn());
const openPlugin = vi.hoisted(() => vi.fn());
const pluginActions = vi.hoisted(() => ({ value: [] as unknown[] }));
const canPlayLocally = vi.hoisted(() => ({ value: true }));

vi.mock("vue-i18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock("@/composables/useGameActions", () => ({
  GAME_ACTIONS_KEY: Symbol("game-actions"),
  useGameActions: () => ({
    canPlayLocally,
    needsLaunchConfirm: { value: false },
    playPath: () => "/ejs/42",
    play,
  }),
}));
vi.mock("@/composables/usePluginActions", () => ({
  usePluginActions: () => ({
    playActions: pluginActions,
    open: openPlugin,
  }),
}));

const deckAction = {
  pluginId: "rommdeck",
  pluginName: "RommDeck",
  id: "open",
  label: "Open in RommDeck",
  icon: "mdi-monitor",
  url: "rommdeck://open?rom={rom_id}",
  href: "rommdeck://open?rom=42",
  open: "new-tab",
  slot: "game.play",
  platforms: [],
};

function render(on: SimpleRom = rom) {
  return mount(PlayButton, { props: { rom: on, size: "default" } });
}

describe("PlayButton", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    canPlayLocally.value = true;
    pluginActions.value = [];
    play.mockReset();
    openPlugin.mockReset();
  });

  it("is absent when nothing can start the game", () => {
    canPlayLocally.value = false;

    expect(render().find("button, a").exists()).toBe(false);
  });

  it("keeps the plain anchor when RomM is the only target", () => {
    const wrapper = render();

    expect(wrapper.find("a").exists()).toBe(true);
    expect(wrapper.find('[aria-label="play.play-with"]').exists()).toBe(false);
  });

  it("still offers Play when only a plugin can start the game", () => {
    canPlayLocally.value = false;
    pluginActions.value = [deckAction];

    const button = render().find("button");

    expect(button.exists()).toBe(true);
    expect(button.attributes("aria-label")).toBe("rom.play");
    expect(button.classes()).toContain("r-game-btn--emphasized");
  });

  it("plays straight away when the plugin is the only target", async () => {
    canPlayLocally.value = false;
    pluginActions.value = [deckAction];

    await render().find("button").trigger("click");

    expect(openPlugin).toHaveBeenCalledWith(deckAction);
  });

  it("asks which one when both RomM and a plugin can play", async () => {
    pluginActions.value = [deckAction];

    const button = render().find('button[aria-label="play.play-with"]');
    await button.trigger("click");

    expect(button.exists()).toBe(true);
    expect(play).not.toHaveBeenCalled();
    expect(openPlugin).not.toHaveBeenCalled();
  });
});
