import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import BottomNav from "./BottomNav.vue";

vi.mock("vue-i18n");
vi.mock("vue-router", () => ({ useRoute: () => ({ path: "/collections" }) }));
vi.mock("@/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(true) }),
}));

describe("BottomNav", () => {
  it("shows the active glyph only on the active tab", () => {
    const wrapper = mount(BottomNav, {
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    const icons = wrapper.findAll(".r-icon").map((i) => i.classes());

    expect(icons[0]).toContain("mdi-home-outline");
    expect(icons[2]).toContain("mdi-bookmark");
    expect(icons[2]).not.toContain("mdi-bookmark-outline");
  });
});
