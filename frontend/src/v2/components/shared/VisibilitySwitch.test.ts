import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import VisibilitySwitch from "./VisibilitySwitch.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe("VisibilitySwitch", () => {
  it("keeps both labels in place and shows the one it is on", async () => {
    const wrapper = mount(VisibilitySwitch, { props: { modelValue: false } });
    const [publicLabel, privateLabel] = wrapper.findAll(
      ".r-visibility-switch__label > span",
    );

    expect(publicLabel.classes()).toContain("r-visibility-switch__off");
    expect(privateLabel.classes()).not.toContain("r-visibility-switch__off");
    expect(wrapper.get("button").attributes("aria-label")).toBe(
      "common.private",
    );

    await wrapper.setProps({ modelValue: true });

    expect(publicLabel.classes()).not.toContain("r-visibility-switch__off");
    expect(privateLabel.classes()).toContain("r-visibility-switch__off");
    expect(wrapper.get("button").attributes("aria-label")).toBe(
      "common.public",
    );
  });

  it("flips its model when clicked", async () => {
    const wrapper = mount(VisibilitySwitch, { props: { modelValue: false } });

    await wrapper.get("button").trigger("click");

    expect(wrapper.emitted("update:modelValue")).toEqual([[true]]);
  });
});
