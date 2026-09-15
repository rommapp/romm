import { mount } from "@vue/test-utils";
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "./GameActionBtn.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: { value: false } }),
}));

const nativeActionLabel = { value: "rom.play-native" };
const nativeLaunching = { value: false };
const play = vi.fn();
const cancelNativeLaunch = vi.fn();

vi.mock("@/v2/composables/useGameActions", () => ({
  GAME_ACTIONS_KEY: Symbol("gameActions"),
  useGameActions: () => ({
    nativeActionLabel,
    nativeLaunching,
    play,
    cancelNativeLaunch,
    isFavorited: { value: false },
    currentStatusKey: { value: null },
  }),
}));

const RIcon = {
  props: { icon: { type: String, default: "" } },
  template: `<i class="icon" :data-icon="icon" />`,
};
const RTooltip = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tooltip">{{ text }}</span>`,
};

function mountNative(withLabel = false) {
  return mount(GameActionBtn, {
    props: {
      rom: { id: 7, rom_user: null } as unknown as SimpleRom,
      action: "native",
      withLabel,
    },
    global: {
      stubs: { RIcon, RTooltip, RMenu: true, RMenuItem: true, RDivider: true },
    },
  });
}

beforeEach(() => {
  play.mockClear();
  cancelNativeLaunch.mockClear();
  nativeLaunching.value = false;
  nativeActionLabel.value = "rom.play-native";
});

describe("GameActionBtn: the native action", () => {
  it("asks for the native player when pressed", async () => {
    const wrapper = mountNative();

    await wrapper.find("button").trigger("click");

    expect(play).toHaveBeenCalledWith("native");
    expect(wrapper.find(".icon").attributes("data-icon")).toBe(
      "mdi-desktop-classic",
    );
  });

  // The button doubles as the launch's progress indicator, so a second press
  // while the shell is working has to mean "stop", not "launch again" (which
  // the shell would refuse as already-running).
  it("cancels instead of relaunching while the shell is working", async () => {
    nativeLaunching.value = true;
    nativeActionLabel.value = "rom.native-downloading";
    const wrapper = mountNative();

    await wrapper.find("button").trigger("click");

    expect(cancelNativeLaunch).toHaveBeenCalledTimes(1);
    expect(play).not.toHaveBeenCalled();
    expect(wrapper.find(".icon").attributes("data-icon")).toBe(
      "mdi-loading mdi-spin",
    );
  });

  it("renders the composable's label as the accessible name", () => {
    nativeActionLabel.value = "rom.play-native-in";

    expect(mountNative().find("button").attributes("aria-label")).toBe(
      "rom.play-native-in",
    );
  });

  it("shows that label as text once it is a pill", () => {
    expect(mountNative(true).text()).toContain("rom.play-native");
  });
});

// An icon name with no glyph behind it renders as an empty button and nothing
// fails, so the name is checked against the font RomM actually ships.
describe("GameActionBtn: the native icon exists", () => {
  const MDI_CSS = readFileSync(
    "node_modules/@mdi/font/css/materialdesignicons.css",
    "utf8",
  );

  it.each(["mdi-desktop-classic", "mdi-loading", "mdi-spin"])(
    "%s is a real class in the bundled font",
    (name) => {
      expect(MDI_CSS).toContain(`.${name}`);
    },
  );
});
