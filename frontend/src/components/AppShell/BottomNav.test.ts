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
  it("uses the filled glyph on every tab", () => {
    const wrapper = mount(BottomNav, {
      global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
    });
    const icons = wrapper.findAll(".r-icon").map((i) => i.classes());

    expect(icons.flat().filter((c) => c.endsWith("-outline"))).toEqual([]);
    expect(icons[0]).toContain("mdi-home");
    expect(icons[2]).toContain("mdi-bookmark");
  });
});
