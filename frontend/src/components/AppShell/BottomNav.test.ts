import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import BottomNav from "./BottomNav.vue";

type AfterEach = (to: unknown, from: unknown, failure?: unknown) => void;
const settled: { fn: AfterEach | null } = { fn: null };
const cancelled = { cancelled: true };

vi.mock("vue-i18n");
vi.mock("vue-router", () => ({
  useRoute: () => ({ path: "/collections" }),
  useRouter: () => ({
    afterEach: (fn: AfterEach) => {
      settled.fn = fn;
      return () => {};
    },
  }),
  isNavigationFailure: (failure: unknown) => failure === cancelled,
  NavigationFailureType: { cancelled: 8 },
}));
vi.mock("@/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(true) }),
}));

const RouterLink = {
  props: { to: String },
  template: '<a :href="to"><slot /></a>',
};

function mountNav() {
  return mount(BottomNav, { global: { stubs: { RouterLink } } });
}

describe("BottomNav", () => {
  it("uses the filled glyph on every tab", () => {
    const wrapper = mountNav();
    const icons = wrapper.findAll(".r-icon").map((i) => i.classes());

    expect(icons.flat().filter((c) => c.endsWith("-outline"))).toEqual([]);
    expect(icons[0]).toContain("mdi-home");
    expect(icons[2]).toContain("mdi-bookmark");
  });

  it("highlights a tapped tab before the route changes", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");
    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");

    await tabs[1]?.trigger("click");

    expect(tabs[1]?.classes()).toContain("r-segmented-control__btn--active");
    expect(tabs[2]?.classes()).not.toContain(
      "r-segmented-control__btn--active",
    );
  });

  it("marks only the active tab as the current page", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    expect(tabs.map((t) => t.attributes("aria-current"))).toEqual([
      undefined,
      undefined,
      "page",
      undefined,
    ]);

    await tabs[1]?.trigger("click");

    expect(tabs[1]?.attributes("aria-current")).toBe("page");
    expect(tabs[2]?.attributes("aria-current")).toBeUndefined();
  });

  it("hands the highlight back to the route once navigation settles", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    settled.fn?.({}, {});
    await wrapper.vm.$nextTick();

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
  });

  it("ignores modified clicks that open in a new tab", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click", { ctrlKey: true });
    await tabs[3]?.trigger("click", { metaKey: true });

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
    expect(tabs[1]?.attributes("aria-current")).toBeUndefined();
  });

  it("keeps the latest tap highlighted when an older navigation is cancelled", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    await tabs[3]?.trigger("click");
    settled.fn?.({}, {}, cancelled);
    await wrapper.vm.$nextTick();

    expect(tabs[3]?.classes()).toContain("r-segmented-control__btn--active");
  });
});
