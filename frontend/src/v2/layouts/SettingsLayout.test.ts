import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import SettingsLayout from "./SettingsLayout.vue";

const { routeMeta, mdAndUp } = vi.hoisted(() => ({
  routeMeta: { value: {} as Record<string, unknown> },
  mdAndUp: { value: true },
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ meta: routeMeta.value }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ mdAndUp: ref(mdAndUp.value) }),
}));

vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));

function mountLayout() {
  return mount(SettingsLayout, {
    global: { stubs: { SettingsSidebar: true, RouterView: true } },
  });
}

function isFill(wrapper: ReturnType<typeof mountLayout>): boolean {
  return wrapper.find("section").classes().includes("r-v2-settings--fill");
}

describe("SettingsLayout fill mode", () => {
  beforeEach(() => {
    routeMeta.value = {};
    mdAndUp.value = true;
  });

  it("fills on every breakpoint for `fill: true`", () => {
    routeMeta.value = { fill: true };
    mdAndUp.value = false;
    expect(isFill(mountLayout())).toBe(true);
  });

  it('fills on desktop for `fill: "desktop"`', () => {
    routeMeta.value = { fill: "desktop" };
    expect(isFill(mountLayout())).toBe(true);
  });

  it('keeps the document scroll on phones for `fill: "desktop"`', () => {
    routeMeta.value = { fill: "desktop" };
    mdAndUp.value = false;
    expect(isFill(mountLayout())).toBe(false);
  });

  it("does not fill without the meta", () => {
    expect(isFill(mountLayout())).toBe(false);
  });
});
