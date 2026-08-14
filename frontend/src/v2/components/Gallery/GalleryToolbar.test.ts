import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import GalleryToolbar from "./GalleryToolbar.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndUp: ref(true) }),
}));

const modality = ref<"mouse" | "pad">("mouse");
vi.mock("@/v2/composables/useInputModality", () => ({
  useInputModality: () => ({ modality }),
}));

function mountToolbar(props: Record<string, unknown> = {}) {
  return mount(GalleryToolbar, {
    attachTo: document.body,
    props: { groupBy: "none", layout: "grid", showSearch: true, ...props },
    global: {
      stubs: {
        RBadge: true,
        RBtn: true,
        RIcon: true,
        RMenu: true,
        RSliderBtnGroup: true,
      },
    },
  });
}

describe("GalleryToolbar search autofocus", () => {
  it("leaves the search field unfocused by default", () => {
    const wrapper = mountToolbar();

    expect(document.activeElement).not.toBe(wrapper.find("input").element);
    wrapper.unmount();
  });

  it("focuses the search field when the view asks for it", () => {
    const wrapper = mountToolbar({ autofocusSearch: true });

    expect(document.activeElement).toBe(wrapper.find("input").element);
    wrapper.unmount();
  });

  it("skips autofocus on a gamepad, which would swallow d-pad navigation", () => {
    modality.value = "pad";
    const wrapper = mountToolbar({ autofocusSearch: true });

    expect(document.activeElement).not.toBe(wrapper.find("input").element);
    modality.value = "mouse";
    wrapper.unmount();
  });
});
