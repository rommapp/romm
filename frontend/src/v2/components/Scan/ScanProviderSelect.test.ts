import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { MetadataOption } from "@/stores/heartbeat";
import ScanProviderSelect from "./ScanProviderSelect.vue";

vi.mock("vue-i18n");

const provider = (value: string, name: string): MetadataOption => ({
  value,
  name,
  logo_path: `/assets/scrappers/${value}.png`,
  disabled: "",
});
const IGDB = provider("igdb", "IGDB");
const LAUNCHBOX = provider("launchbox", "LaunchBox");

// Renders every item through the `#item` slot so the rows are inspectable.
const RSelect = {
  props: {
    modelValue: { type: Array, default: () => [] },
    items: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue", "update:all-selected"],
  template: `<div class="select">
    <div v-for="item in items" :key="item.value" class="row">
      <slot name="item" :item="{ raw: item }" :props="{}" />
    </div>
  </div>`,
};

function mountSelect(props: Record<string, unknown> = {}) {
  return mount(ScanProviderSelect, {
    props: {
      items: [IGDB, LAUNCHBOX],
      label: "General",
      icon: "mdi-database-search",
      modelValue: [],
      ...props,
    },
    global: { stubs: { RSelect, RAvatar: true, RTooltip: true } },
  });
}

describe("ScanProviderSelect", () => {
  it("forwards source selection and the all-selected flag", async () => {
    const wrapper = mountSelect();
    const select = wrapper.getComponent(RSelect);

    await select.vm.$emit("update:modelValue", [IGDB]);
    await select.vm.$emit("update:all-selected", true);

    expect(wrapper.emitted("update:modelValue")).toEqual([[[IGDB]]]);
    expect(wrapper.emitted("update:allSelected")).toEqual([[true]]);
  });

  it("omits the LaunchBox toggle unless launchbox-remote is bound", () => {
    const wrapper = mountSelect();

    expect(wrapper.find('[role="switch"]').exists()).toBe(false);
  });

  it("toggles the LaunchBox source from its labelled switch", async () => {
    const wrapper = mountSelect({
      launchboxRemote: false,
      launchboxSelected: true,
    });
    const toggle = wrapper.get('[role="switch"]');

    expect(toggle.attributes("aria-label")).toBe("rom.launchbox-cloud-source");
    await toggle.trigger("click");
    expect(wrapper.emitted("update:launchboxRemote")).toEqual([[true]]);
  });

  it("disables the LaunchBox switch until LaunchBox is selected", () => {
    const wrapper = mountSelect({ launchboxRemote: false });

    expect(wrapper.get('[role="switch"]').attributes("disabled")).toBeDefined();
  });
});
