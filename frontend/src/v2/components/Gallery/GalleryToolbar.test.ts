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

// The sort-axis control lives inside an RMenu, so its entries only exist
// once the menu renders its slots.
const RMenuPassthrough = {
  name: "RMenuPassthrough",
  template: `<div><slot name="activator" :props="{}" /><slot /></div>`,
};

function mountToolbar(
  props: Record<string, unknown> = {},
  menuStub: boolean | typeof RMenuPassthrough = true,
) {
  return mount(GalleryToolbar, {
    attachTo: document.body,
    props: { groupBy: "none", layout: "grid", showSearch: true, ...props },
    global: {
      stubs: {
        RBadge: true,
        RBtn: true,
        RIcon: true,
        RMenu: menuStub,
        RSliderBtnGroup: true,
      },
    },
  });
}

const SORT_OPTIONS = [
  { key: "name", label: "Title" },
  { key: "fs_size_bytes", label: "Size" },
] as const;

function mountWithSortOptions(props: Record<string, unknown> = {}) {
  return mountToolbar(
    { sortKey: "name", sortKeyItems: SORT_OPTIONS, ...props },
    RMenuPassthrough,
  );
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
    const withAxes = mountWithSortOptions();
    const menusWithAxes = withAxes.findAllComponents(RMenuPassthrough).length;
    withAxes.unmount();

    const wrapper = mountWithSortOptions({ sortKeyItems: [] });

    expect(wrapper.findAllComponents(RMenuPassthrough)).toHaveLength(
      menusWithAxes - 1,
    );
    expect(sortItems(wrapper)).toHaveLength(0);
    wrapper.unmount();
  });

  // List mode sorts through the column headers, so the toolbar's axis
  // control steps aside rather than offer a second, competing one.
  it("drops the control in list mode only", () => {
    const grid = mountWithSortOptions({ layout: "grid" });
    const menusInGrid = grid.findAllComponents(RMenuPassthrough).length;
    grid.unmount();

    const wrapper = mountWithSortOptions({ layout: "list" });

    expect(wrapper.findAllComponents(RMenuPassthrough)).toHaveLength(
      menusInGrid - 1,
    );
    expect(sortItems(wrapper)).toHaveLength(0);
    wrapper.unmount();
  });
});
