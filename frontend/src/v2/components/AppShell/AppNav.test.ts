import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { computed, nextTick, ref } from "vue";
import AppNav from "./AppNav.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useNavDestinations", () => ({
  useNavDestinations: () => ({
    destinations: computed(() => []),
    activeId: computed(() => "home"),
  }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(false) }),
}));

vi.mock("@/v2/components/AppShell/ScanningIndicator.vue", () => ({
  default: { template: "<div />" },
}));
vi.mock("@/v2/components/AppShell/UserMenu.vue", () => ({
  default: { template: "<div />" },
}));
vi.mock("@/v2/components/Soundtrack/NowPlayingPill.vue", () => ({
  default: { template: "<div />" },
}));

function scrollWindowTo(y: number) {
  document.documentElement.scrollTop = y;
  window.dispatchEvent(new Event("scroll"));
}

function mountNav() {
  return mount(AppNav, {
    global: { stubs: { RouterLink: true, RImg: true, RSliderBtnGroup: true } },
  });
}

const SCROLLED = "r-v2-nav-bar--scrolled";

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
