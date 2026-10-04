import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { ScanTypeOption } from "@/v2/types/scan";
import ScanTypeSelect from "./ScanTypeSelect.vue";

vi.mock("vue-i18n");

// Renders every item through the `#item` slot so the rows are inspectable.
const RSelect = {
  props: {
    modelValue: { type: String, default: "" },
    items: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue"],
  template: `<div class="select">
    <div v-for="item in items" :key="item.value" class="row">
      <slot name="item" :item="{ title: item.title, raw: item }" :props="{}" />
    </div>
  </div>`,
};

const ITEMS: ScanTypeOption[] = [
  { title: "Quick", subtitle: "Only new files", value: "quick" },
  {
    title: "Hashes",
    subtitle: "Recalculate hashes",
    value: "hashes",
    disabled: "Hash calculation is off",
  },
];

function mountSelect() {
  return mount(ScanTypeSelect, {
    props: { items: ITEMS, modelValue: "quick" },
    global: { stubs: { RSelect } },
  });
}

describe("ScanTypeSelect", () => {
  it("shows each option's description, or why it is disabled", () => {
    const subtitles = mountSelect()
      .findAll(".r-select__item-subtitle")
      .map((s) => s.text());

    expect(subtitles).toEqual(["Only new files", "Hash calculation is off"]);
  });

  it("forwards the picked scan type", async () => {
    const wrapper = mountSelect();

    await wrapper.getComponent(RSelect).vm.$emit("update:modelValue", "hashes");

    expect(wrapper.emitted("update:modelValue")).toEqual([["hashes"]]);
  });
});
