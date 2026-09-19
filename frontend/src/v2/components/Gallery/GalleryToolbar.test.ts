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

// The sort-axis control lives inside an RMenu, so its entries only exist
// once the menu renders its slots.
const RMenuPassthrough = {
  template: `<div><slot name="activator" :props="{}" /><slot /></div>`,
};

const SORT_OPTIONS = [
  { key: "name", label: "Title" },
  { key: "fs_size_bytes", label: "Size" },
] as const;

function mountWithSortOptions(props: Record<string, unknown> = {}) {
  return mount(GalleryToolbar, {
    attachTo: document.body,
    props: {
      groupBy: "none",
      layout: "grid",
      sortKey: "name",
      sortKeyItems: SORT_OPTIONS,
      ...props,
    },
    global: {
      stubs: {
        RBadge: true,
        RBtn: true,
        RIcon: true,
        RMenu: RMenuPassthrough,
        RSliderBtnGroup: true,
      },
    },
  });
}

function sortItems(wrapper: ReturnType<typeof mountWithSortOptions>) {
  return wrapper
    .findAllComponents({ name: "RMenuItem" })
    .filter((item) =>
      SORT_OPTIONS.some((option) => option.label === item.props("label")),
    );
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

describe("GalleryToolbar sort axis", () => {
  it("emits the picked axis so grid mode can change the sort key", async () => {
    const wrapper = mountWithSortOptions();

    const size = sortItems(wrapper).find(
      (item) => item.props("label") === "Size",
    );
    expect(size).toBeTruthy();
    await size!.trigger("click");

    expect(wrapper.emitted("update:sortKey")).toEqual([["fs_size_bytes"]]);
    wrapper.unmount();
  });

  it("marks the active axis", () => {
    const wrapper = mountWithSortOptions({ sortKey: "fs_size_bytes" });

    const variants = Object.fromEntries(
      sortItems(wrapper).map((item) => [
        item.props("label"),
        item.props("variant"),
      ]),
    );

    expect(variants).toMatchObject({ Size: "active", Title: "default" });
    wrapper.unmount();
  });

  // Index views (Platforms / Collections) sort their own tiles and pass
  // no axes; the control must not paint an empty menu for them.
  it("hides the control when no axes are offered", () => {
    const wrapper = mountWithSortOptions({ sortKeyItems: [] });

    expect(sortItems(wrapper)).toHaveLength(0);
    wrapper.unmount();
  });
});
