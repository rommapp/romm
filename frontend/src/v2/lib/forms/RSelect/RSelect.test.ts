import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RSelect from "./RSelect.vue";

// Regression guard: `.r-select__value` is a flex row with a 6px gap (it
// spaces chips apart). A multi-select without chips renders its titles and
// the "," separator as plain spans, so hoisting them into that row put the
// gap on both sides of the comma and the activator read "A , B".
describe("RSelect multi-select without chips", () => {
  const items = [
    { title: "Screenshot", value: "screenshot" },
    { title: "Manual", value: "manual" },
  ];

  it("keeps the titles and separator in one box inside the value row", () => {
    const wrapper = mount(RSelect, {
      props: { items, multiple: true, modelValue: ["screenshot", "manual"] },
    });

    const value = wrapper.get(".r-select__value");
    expect(value.element.children).toHaveLength(1);

    const selection = wrapper.get(".r-select__selection");
    expect(selection.findAll(".r-select__title").map((n) => n.text())).toEqual([
      "Screenshot",
      "Manual",
    ]);
    expect(selection.findAll(".r-select__sep")).toHaveLength(1);
    expect(selection.text()).toBe("Screenshot, Manual");
  });
});
