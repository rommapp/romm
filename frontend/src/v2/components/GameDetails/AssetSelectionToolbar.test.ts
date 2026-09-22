import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AssetSelectionToolbar from "./AssetSelectionToolbar.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    // Keeps the count, so a wrong pluralisation argument fails the assertion.
    t: (key: string, count?: number) =>
      typeof count === "number" ? `${key}:${count}` : key,
  }),
}));

const RCheckbox = {
  props: {
    modelValue: { type: Boolean, default: false },
    indeterminate: { type: Boolean, default: false },
  },
  emits: ["update:modelValue"],
  template: `<input type="checkbox" class="all" :checked="modelValue" :data-indeterminate="indeterminate" @change="$emit('update:modelValue', !modelValue)" />`,
};
const RBtn = {
  props: { ariaLabel: { type: String, default: "" } },
  emits: ["click"],
  template: `<button class="btn" :aria-label="ariaLabel" @click="$emit('click')" />`,
};

function toolbar(
  props: Partial<InstanceType<typeof AssetSelectionToolbar>["$props"]> = {},
) {
  return mount(AssetSelectionToolbar, {
    props: {
      count: 0,
      total: 3,
      allChecked: false,
      someChecked: false,
      allFavorite: false,
      ...props,
    },
    global: { stubs: { RCheckbox, RBtn } },
  });
}

describe("AssetSelectionToolbar", () => {
  it("counts the list until something is checked, then the selection", () => {
    expect(toolbar().get(".r-v2-asset-select__status").text()).toBe(
      "rom.assets-count-n:3",
    );
    expect(toolbar().findAll(".btn")).toHaveLength(0);

    const some = toolbar({ count: 2, someChecked: true });

    expect(some.get(".r-v2-asset-select__status").text()).toBe(
      "rom.assets-selected-of",
    );
    expect(some.findAll(".btn").map((b) => b.attributes("aria-label"))).toEqual(
      [
        "rom.add-to-favorites",
        "rom.add-labels",
        "common.delete",
        "common.clear",
      ],
    );
  });

  it("shows the select-all box as mixed only on a partial selection", () => {
    expect(
      toolbar({ count: 2, someChecked: true })
        .get(".all")
        .attributes("data-indeterminate"),
    ).toBe("true");
    expect(
      toolbar({ count: 3, allChecked: true })
        .get(".all")
        .attributes("data-indeterminate"),
    ).toBe("false");
  });

  it("offers to clear the hearts once every checked item is a favorite", () => {
    const wrapper = toolbar({ count: 3, allChecked: true, allFavorite: true });

    expect(wrapper.findAll(".btn")[0].attributes("aria-label")).toBe(
      "rom.remove-from-favorites",
    );
  });

  it("emits one event per action", async () => {
    const wrapper = toolbar({ count: 1, someChecked: true });
    const buttons = wrapper.findAll(".btn");

    await wrapper.get(".all").trigger("change");
    await buttons[0].trigger("click");
    await buttons[1].trigger("click");
    await buttons[2].trigger("click");
    await buttons[3].trigger("click");

    expect(wrapper.emitted("toggleAll")).toHaveLength(1);
    expect(wrapper.emitted("toggleFavorite")).toHaveLength(1);
    expect(wrapper.emitted("editLabels")).toHaveLength(1);
    expect(wrapper.emitted("delete")).toHaveLength(1);
    expect(wrapper.emitted("clear")).toHaveLength(1);
  });
});
