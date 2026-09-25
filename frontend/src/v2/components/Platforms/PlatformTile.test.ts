import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import PlatformTile from "./PlatformTile.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en" } }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@v2/lib", () => ({
  RPlatformIcon: defineComponent({ template: "<i />" }),
}));

vi.mock("@/v2/composables/usePlatformPlayable", () => ({
  usePlatformPlayable: () => ({
    emulator: { value: null },
    mode: { value: null },
    streamLabel: { value: null },
  }),
}));

describe("PlatformTile", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  // The class is the cell selector PlatformsIndex hands useWrapGridNav; losing
  // it takes arrow and gamepad navigation off the whole platforms grid.
  it("marks its root as a spatial-nav cell", () => {
    const wrapper = mount(PlatformTile, {
      props: { slug: "snes", displayName: "SNES", id: 1, variant: "grid" },
      global: { stubs: { RouterLink: true } },
    });

    expect(wrapper.find(".plat-tile").exists()).toBe(true);
  });
});
