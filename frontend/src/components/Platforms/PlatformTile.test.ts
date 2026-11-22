import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import PlatformTile from "./PlatformTile.vue";

vi.mock("vue-i18n");

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/shared/PlatformIcon.vue", () => ({
  default: defineComponent({ template: "<i />" }),
}));

vi.mock("@/composables/usePlatformPlayable", () => ({
  usePlatformPlayable: () => ({
    emulator: ref(null),
    mode: ref(null),
    streamLabel: ref(null),
  }),
}));

describe("PlatformTile", () => {
  // The class is the cell selector PlatformsIndex hands useGridNav; losing it
  // takes arrow and gamepad navigation off the whole platforms grid.
  it("marks its root as a spatial-nav cell", () => {
    const wrapper = mount(PlatformTile, {
      props: { slug: "snes", displayName: "SNES", id: 1, variant: "grid" },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });

    expect(wrapper.find(".plat-tile").exists()).toBe(true);
  });

  it("shows discovery metadata and falls back when artwork fails", async () => {
    const wrapper = mount(PlatformTile, {
      props: {
        slug: "unlisted-platform",
        displayName: "SNES",
        id: 1,
        variant: "grid",
        category: "portable_console",
        firstReleaseYear: 1990,
        artworkUrl: "/hardware.png",
        romCount: 42,
      },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    expect(wrapper.text()).toContain("1990 · Portable Console");
    expect(wrapper.find("img").attributes("src")).toBe("/hardware.png");
    await wrapper.find("img").trigger("error");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".plat-tile__icon-inner i").exists()).toBe(true);
  });

  it("keeps dashboard rows compact and omits unavailable metadata", () => {
    const wrapper = mount(PlatformTile, {
      props: {
        slug: "unlisted-platform",
        displayName: "SNES",
        artworkUrl: "/hardware.png",
        firstReleaseYear: 1990,
        category: "console",
      },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find(".plat-tile__metadata").exists()).toBe(false);
  });

  it("omits metadata when the platform is unidentified", () => {
    const wrapper = mount(PlatformTile, {
      props: { slug: "custom", displayName: "My platform", variant: "grid" },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    expect(wrapper.find(".plat-tile__metadata").exists()).toBe(false);
    expect(wrapper.text()).toBe("My platform");
  });

  it("prefers curated platform icons over provider variant logos", () => {
    const wrapper = mount(PlatformTile, {
      props: {
        slug: "n64",
        displayName: "Nintendo 64",
        variant: "grid",
        artworkUrl: "/variant.png",
      },
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    expect(wrapper.find(".r-image").exists()).toBe(false);
  });
});
