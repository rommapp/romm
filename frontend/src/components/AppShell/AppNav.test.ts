import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { computed, nextTick, ref } from "vue";
import AppNav from "./AppNav.vue";

vi.mock("vue-i18n");

vi.mock("@/composables/useNavDestinations", () => ({
  useNavDestinations: () => ({
    destinations: computed(() => []),
    activeId: computed(() => "home"),
  }),
}));

vi.mock("@/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(false) }),
}));

vi.mock("@/components/AppShell/ConvertingIndicator.vue", () => ({
  default: { template: "<div />" },
}));
vi.mock("@/components/AppShell/ScanningIndicator.vue", () => ({
  default: { template: "<div />" },
}));
vi.mock("@/components/AppShell/UserMenu.vue", () => ({
  default: { template: "<div />" },
}));
vi.mock("@/components/Soundtrack/NowPlayingPill.vue", () => ({
  default: { template: "<div />" },
}));

function scrollWindowTo(y: number) {
  document.documentElement.scrollTop = y;
  window.dispatchEvent(new Event("scroll"));
}

function mountNav() {
  return mount(AppNav, {
    global: {
      stubs: { RouterLink: true, RImg: true, RSegmentedControl: true },
    },
  });
}

const SCROLLED = "r-nav-bar--scrolled";

describe("AppNav glass", () => {
  afterEach(() => {
    document.documentElement.scrollTop = 0;
  });

  it("turns to glass once the window scrolls past the threshold", async () => {
    const wrapper = mountNav();
    expect(wrapper.classes()).not.toContain(SCROLLED);

    scrollWindowTo(40);
    await nextTick();
    expect(wrapper.classes()).toContain(SCROLLED);

    scrollWindowTo(0);
    await nextTick();
    expect(wrapper.classes()).not.toContain(SCROLLED);
  });

  it("stays clear at a scroll within the threshold", async () => {
    const wrapper = mountNav();

    scrollWindowTo(2);
    await nextTick();

    expect(wrapper.classes()).not.toContain(SCROLLED);
  });

  it("starts as glass when mounted on an already-scrolled page", async () => {
    document.documentElement.scrollTop = 40;
    const wrapper = mountNav();
    await nextTick();

    expect(wrapper.classes()).toContain(SCROLLED);
  });
});
