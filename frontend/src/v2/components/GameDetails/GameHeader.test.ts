import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { makeDetailedRom } from "@/utils/rom.fixtures";
import GameHeader from "./GameHeader.vue";

const { showLogoTitle } = vi.hoisted(() => ({
  showLogoTitle: { value: false },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({ showLogoTitle }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(false), xs: ref(false) }),
}));

vi.mock("@/v2/composables/useGameActions", () => ({
  useGameActions: () => ({ platformPath: ref(null) }),
}));

function mountHeader(logoPath: string | null) {
  const rom = makeDetailedRom({
    id: 1,
    ss_metadata: { logo_path: logoPath },
    sibling_roms: [],
  });
  return mount(GameHeader, {
    props: {
      rom,
      title: "Chrono Trigger",
      platformLabel: "SNES",
      releaseDate: null,
      verified: false,
      regions: [],
      languages: [],
      tags: [],
    },
    global: {
      stubs: {
        GameActions: true,
        PrevNextNav: true,
        VersionSwitcher: true,
        MainSiblingToggle: true,
        PlatformIcon: true,
        RouterLink: true,
      },
    },
  });
}

describe("GameHeader", () => {
  beforeEach(() => {
    showLogoTitle.value = false;
  });

  it("shows the title text when the logo setting is off", () => {
    const wrapper = mountHeader("roms/1/1/logo/logo.png");
    expect(wrapper.find("h1 img").exists()).toBe(false);
    expect(wrapper.find("h1").text()).toBe("Chrono Trigger");
  });

  it("shows the logo in place of the title when the setting is on", () => {
    showLogoTitle.value = true;
    const img = mountHeader("roms/1/1/logo/logo.png").find("h1 img");
    expect(img.attributes("src")).toContain("roms/1/1/logo/logo.png");
    expect(img.attributes("alt")).toBe("Chrono Trigger");
  });

  it("falls back to the title text when the rom has no logo", () => {
    showLogoTitle.value = true;
    const wrapper = mountHeader(null);
    expect(wrapper.find("h1 img").exists()).toBe(false);
    expect(wrapper.find("h1").text()).toBe("Chrono Trigger");
  });

  it("falls back to the title text when the logo fails to load", async () => {
    showLogoTitle.value = true;
    const wrapper = mountHeader("roms/1/1/logo/logo.png");
    await wrapper.find("h1 img").trigger("error");
    expect(wrapper.find("h1 img").exists()).toBe(false);
    expect(wrapper.find("h1").text()).toBe("Chrono Trigger");
  });

  it.each([
    // Square: the height cap binds before the shared area does.
    { width: 512, height: 512, expected: "176px" },
    // Wide: sized to the shared area, so it ends up shorter than the cap.
    { width: 1024, height: 256, expected: "400px" },
  ])(
    "sizes a $width x $height logo to $expected wide",
    async ({ width, height, expected }) => {
      showLogoTitle.value = true;
      const wrapper = mountHeader("roms/1/1/logo/logo.png");
      const img = wrapper.find("h1 img");
      Object.defineProperty(img.element, "naturalWidth", { value: width });
      Object.defineProperty(img.element, "naturalHeight", { value: height });
      await img.trigger("load");
      expect((img.element as HTMLImageElement).style.width).toBe(expected);
    },
  );
});
