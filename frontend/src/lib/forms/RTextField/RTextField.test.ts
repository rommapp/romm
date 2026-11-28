import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import RTextField from "./RTextField.vue";

const POPUP = {
  controls: "popup-1",
  expanded: false,
  kind: "dialog",
} as const;

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

describe("RTextField required", () => {
  function tooltip(wrapper: ReturnType<typeof mount>) {
    return wrapper.findComponent({ name: "RTooltip" });
  }

  it("announces it without the browser's own validation", () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "", required: true },
    });

    const input = wrapper.get("input");
    expect(input.attributes("aria-required")).toBe("true");
    expect(input.attributes("required")).toBeUndefined();
    wrapper.unmount();
  });

  it("says so in a tooltip only while it's empty", async () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "", required: true },
    });

    expect(tooltip(wrapper).props("text")).toBe("Required");
    expect(tooltip(wrapper).props("disabled")).toBe(false);

    await wrapper.setProps({ modelValue: "RomM" });
    expect(tooltip(wrapper).props("disabled")).toBe(true);
    wrapper.unmount();
  });

  it("keeps quiet on a field that isn't required", () => {
    const wrapper = mount(RTextField, { props: { modelValue: "" } });

    expect(wrapper.get("input").attributes("aria-required")).toBeUndefined();
    expect(tooltip(wrapper).props("disabled")).toBe(true);
    wrapper.unmount();
  });
});

describe("RTextField autofocus", () => {
  // RDialog focuses `[autofocus]` on open, ahead of its own close button.
  it("marks the native field for the surface that opens it", () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "", autofocus: true },
    });
    expect(wrapper.get("input").attributes("autofocus")).toBeDefined();
    wrapper.unmount();
  });

  it("leaves the attribute off unless asked", () => {
    const wrapper = mount(RTextField, { props: { modelValue: "" } });
    expect(wrapper.get("input").attributes("autofocus")).toBeUndefined();
    wrapper.unmount();
  });
});

describe("RTextField native input attributes", () => {
  it("puts inputmode, min and step on the input, not the wrapper", () => {
    const wrapper = mount(RTextField, {
      props: {
        modelValue: "",
        type: "number",
        inputmode: "numeric",
        min: 0,
        step: 1,
      },
    });
    const input = wrapper.get("input");
    expect(input.attributes("inputmode")).toBe("numeric");
    expect(input.attributes("min")).toBe("0");
    expect(input.attributes("step")).toBe("1");
    const outer = wrapper.get(".r-text-field");
    expect(outer.attributes("inputmode")).toBeUndefined();
    expect(outer.attributes("min")).toBeUndefined();
    expect(outer.attributes("step")).toBeUndefined();
    wrapper.unmount();
  });

  it("leaves them off unless asked", () => {
    const wrapper = mount(RTextField, { props: { modelValue: "" } });
    const input = wrapper.get("input");
    expect(input.attributes("inputmode")).toBeUndefined();
    expect(input.attributes("min")).toBeUndefined();
    expect(input.attributes("step")).toBeUndefined();
    wrapper.unmount();
  });
});

describe("RTextField attribute routing", () => {
  it("sends unknown attributes to the input", () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "" },
      attrs: { "aria-label": "Search", spellcheck: "false", title: "Hint" },
    });
    const input = wrapper.get("input");
    expect(input.attributes("aria-label")).toBe("Search");
    expect(input.attributes("spellcheck")).toBe("false");
    expect(input.attributes("title")).toBe("Hint");
    const outer = wrapper.get(".r-text-field");
    expect(outer.attributes("aria-label")).toBeUndefined();
    expect(outer.attributes("spellcheck")).toBeUndefined();
    wrapper.unmount();
  });

  it("keeps class, style, data attributes and listeners on the root", async () => {
    const onClick = vi.fn();
    const wrapper = mount(RTextField, {
      props: { modelValue: "" },
      attrs: {
        class: "mine",
        style: "width: 10px",
        "data-testid": "field",
        onClick,
      },
    });
    const outer = wrapper.get(".r-text-field");
    expect(outer.classes()).toContain("mine");
    expect(outer.attributes("style")).toContain("width: 10px");
    expect(outer.attributes("data-testid")).toBe("field");
    expect(wrapper.get("input").attributes("data-testid")).toBeUndefined();
    await outer.trigger("click");
    expect(onClick).toHaveBeenCalledOnce();
    wrapper.unmount();
  });

  it("lets an aria-label attribute replace the one derived from label", () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "", label: "Name" },
      attrs: { "aria-label": "Search names" },
    });
    expect(wrapper.get("input").attributes("aria-label")).toBe("Search names");
    wrapper.unmount();
  });

  it("routes the same way for a multiline field", () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "", multiline: true },
      attrs: { spellcheck: "false", "data-testid": "field" },
    });
    expect(wrapper.get("textarea").attributes("spellcheck")).toBe("false");
    expect(wrapper.get(".r-text-field").attributes("data-testid")).toBe(
      "field",
    );
    wrapper.unmount();
  });
});

describe("RTextField rules", () => {
  const required = (v: string) => !!v || "Required";

  function details(wrapper: ReturnType<typeof mount>) {
    return wrapper.find(".r-text-field__details--error");
  }

  it("stays quiet until the first blur, then tracks every edit", async () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "", rules: [required] },
    });
    expect(details(wrapper).exists()).toBe(false);

    await wrapper.get("input").trigger("blur");
    expect(details(wrapper).text()).toBe("Required");

    await wrapper.setProps({ modelValue: "RomM" });
    expect(details(wrapper).exists()).toBe(false);
    wrapper.unmount();
  });

  it("re-checks a touched field when its rules change", async () => {
    const wrapper = mount(RTextField, {
      props: { modelValue: "abc", rules: [] },
    });
    await wrapper.get("input").trigger("blur");
    expect(details(wrapper).exists()).toBe(false);

    await wrapper.setProps({ rules: [() => "Passwords don't match"] });
    expect(details(wrapper).text()).toBe("Passwords don't match");

    wrapper.vm.reset();
    await nextTick();
    expect(details(wrapper).exists()).toBe(false);
    wrapper.unmount();
  });
});
