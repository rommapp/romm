import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import {
  isTransitionSkipped,
  settleSkippedTransition,
} from "@/plugins/transition";
import BottomNav from "./BottomNav.vue";

type Target = { fullPath: string };
const hooks: {
  before: ((to: Target) => void) | null;
  after: ((to: Target) => void) | null;
  onError: ((error: unknown, to: Target) => void) | null;
} = { before: null, after: null, onError: null };

vi.mock("vue-i18n");
vi.mock("vue-router", () => ({
  useRoute: () => ({ path: "/collections" }),
  useRouter: () => ({
    beforeEach: (fn: (to: Target) => void) => {
      hooks.before = fn;
      return () => {};
    },
    afterEach: (fn: (to: Target) => void) => {
      hooks.after = fn;
      return () => {};
    },
    onError: (fn: (error: unknown, to: Target) => void) => {
      hooks.onError = fn;
      return () => {};
    },
  }),
}));
vi.mock("@/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(true) }),
}));

// Records what the router would see when RouterLink navigates on click.
const skippedAtNavigation: boolean[] = [];
const RouterLink = defineComponent({
  props: { to: { type: String, required: true } },
  setup(props) {
    const navigate = () =>
      skippedAtNavigation.push(isTransitionSkipped({ fullPath: props.to }));
    return { navigate };
  },
  template: '<a :href="to" @click="navigate"><slot /></a>',
});

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
    hooks.before?.({ fullPath: "/platforms" });
    hooks.after?.({ fullPath: "/platforms" });
    await wrapper.vm.$nextTick();

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
  });

  it("skips the view transition before RouterLink navigates", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");
    skippedAtNavigation.length = 0;

    await tabs[1]?.trigger("click");

    expect(skippedAtNavigation).toEqual([true]);
    settleSkippedTransition({ fullPath: "/platforms" });
  });

  it("ignores modified clicks that open in a new tab", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click", { ctrlKey: true });
    await tabs[3]?.trigger("click", { metaKey: true });

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
    expect(tabs[1]?.attributes("aria-current")).toBeUndefined();
  });

  it("follows a tap on the active tab made while another navigation is pending", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    await tabs[2]?.trigger("click");

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
    expect(tabs[1]?.classes()).not.toContain(
      "r-segmented-control__btn--active",
    );
  });

  it("keeps the latest tap highlighted when an older navigation settles", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    hooks.before?.({ fullPath: "/platforms" });
    await tabs[3]?.trigger("click");
    hooks.before?.({ fullPath: "/search" });
    hooks.after?.({ fullPath: "/platforms" });
    await wrapper.vm.$nextTick();

    expect(tabs[3]?.classes()).toContain("r-segmented-control__btn--active");
  });

  it("hands the highlight back when the latest navigation errors", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    hooks.before?.({ fullPath: "/platforms" });
    hooks.onError?.(new Error("chunk"), { fullPath: "/platforms" });
    await wrapper.vm.$nextTick();

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
  });

  it("ignores errors from a navigation a newer tap superseded", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    hooks.before?.({ fullPath: "/platforms" });
    await tabs[3]?.trigger("click");
    hooks.before?.({ fullPath: "/search" });
    hooks.onError?.(new Error("chunk"), { fullPath: "/platforms" });
    await wrapper.vm.$nextTick();

    expect(tabs[3]?.classes()).toContain("r-segmented-control__btn--active");
  });

  it("hands the highlight back when a navigation started outside the bar fails", async () => {
    const wrapper = mountNav();
    const tabs = wrapper.findAll(".r-segmented-control__btn");

    await tabs[1]?.trigger("click");
    hooks.before?.({ fullPath: "/platforms" });
    hooks.before?.({ fullPath: "/rom/1" });
    hooks.after?.({ fullPath: "/platforms" });
    hooks.onError?.(new Error("chunk"), { fullPath: "/rom/1" });
    await wrapper.vm.$nextTick();

    expect(tabs[2]?.classes()).toContain("r-segmented-control__btn--active");
  });
});
