import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import type { SteamTarget } from "@/v2/composables/useGameActions";
import GameActionBtn from "./GameActionBtn.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: { value: false } }),
}));

// Only the Steam surface is exercised here; everything else the composable
// returns is inert.
const steam = {
  targets: [] as SteamTarget[],
  added: false,
  label: "rom.steam-add",
  disabled: (target: SteamTarget) => target.supported === false,
  toggle: vi.fn(),
};

vi.mock("@/v2/composables/useGameActions", () => ({
  GAME_ACTIONS_KEY: Symbol("test:gameActions"),
  useGameActions: () => ({
    steamTargets: {
      get value() {
        return steam.targets;
      },
    },
    steamAdded: {
      get value() {
        return steam.added;
      },
    },
    steamActionLabel: {
      get value() {
        return steam.label;
      },
    },
    steamTargetLabel: (target: SteamTarget) => `label:${target.device.id}`,
    steamTargetDisabled: steam.disabled,
    toggleSteam: steam.toggle,
    isFavorited: { value: false },
    currentStatusKey: { value: null },
  }),
}));

function target(id: string, supported: boolean | null): SteamTarget {
  return {
    device: { id, name: id } as SteamTarget["device"],
    shortcut: null,
    supported,
  };
}

const RMenu = {
  props: ["modelValue"],
  template: `<div class="menu"><slot name="activator" :props="{}" /><div class="menu-items"><slot /></div></div>`,
};
const RMenuItem = {
  props: ["label", "disabled"],
  template: `<li class="item" :data-disabled="disabled">{{ label }}</li>`,
};
const passthrough = { template: `<span />` };

function mountSteam(targets: SteamTarget[]) {
  steam.targets = targets;
  steam.toggle.mockReset();
  return mount(GameActionBtn, {
    props: { rom: { id: 1 } as SimpleRom, action: "steam" },
    global: {
      stubs: { RMenu, RMenuItem, RIcon: passthrough, RTooltip: passthrough },
    },
  });
}

describe("GameActionBtn steam action", () => {
  it("acts on a single companion directly", async () => {
    const wrapper = mountSteam([target("desktop", true)]);
    expect(wrapper.find(".menu").exists()).toBe(false);
    await wrapper.find("button").trigger("click");
    expect(steam.toggle).toHaveBeenCalledWith(steam.targets[0]);
  });

  it("disables the button when the only companion cannot play the platform", async () => {
    const wrapper = mountSteam([target("desktop", false)]);
    const btn = wrapper.find("button");
    expect(btn.attributes("aria-disabled")).toBe("true");
    await btn.trigger("click");
    expect(steam.toggle).not.toHaveBeenCalled();
  });

  it("opens a picker with one row per companion when there are several", () => {
    const wrapper = mountSteam([
      target("desktop", true),
      target("laptop", false),
    ]);
    const items = wrapper.findAll(".item");
    expect(items.map((i) => i.text())).toEqual([
      "label:desktop",
      "label:laptop",
    ]);
    expect(items[1]?.attributes("data-disabled")).toBe("true");
  });
});
