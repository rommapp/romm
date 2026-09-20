import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import RTextField from "./RTextField.vue";

const POPUP = {
  controls: "popup-1",
  expanded: false,
  kind: "dialog",
} as const;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RTextField popup wiring", () => {
  it("puts the combobox role on the input, not the outer element", () => {
    const wrapper = mount(RTextField, {
      props: {
        modelValue: "",
        prefixLabel: "stacked",
        label: "When",
        popup: POPUP,
      },
    });

    const input = wrapper.get("input");
    expect(input.attributes("role")).toBe("combobox");
    expect(input.attributes("aria-haspopup")).toBe("dialog");
    expect(input.attributes("aria-controls")).toBe("popup-1");
    // The outer element is a <label> here, where the role is disallowed.
    const outer = wrapper.get("label.r-text-field");
    expect(outer.attributes("role")).toBeUndefined();
    wrapper.unmount();
  });

  it("carries no combobox attributes without the prop", () => {
    const wrapper = mount(RTextField, { props: { modelValue: "" } });
    expect(wrapper.get("input").attributes("role")).toBeUndefined();
    wrapper.unmount();
  });

  it("reports the conflict rather than dropping the ARIA silently", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const wrapper = mount(RTextField, {
      props: { modelValue: "", multiline: true, popup: POPUP },
    });

    expect(wrapper.find("textarea").exists()).toBe(true);
    expect(error).toHaveBeenCalledWith(
      expect.stringContaining("`popup` is ignored when `multiline` is set"),
    );
    wrapper.unmount();
  });
});
