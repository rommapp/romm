import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { withoutCdn } from "./markdownNoCdn";

const Editor = defineComponent({
  props: {
    modelValue: { type: String, default: "" },
    noHighlight: { type: Boolean, default: false },
    noKatex: { type: Boolean, default: false },
    noMermaid: { type: Boolean, default: false },
    noEcharts: { type: Boolean, default: false },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    return () =>
      h("button", { onClick: () => emit("update:modelValue", "next") }, [
        props.modelValue,
      ]);
  },
});

describe("withoutCdn", () => {
  it("turns off every CDN-loaded renderer", () => {
    const inner = mount(withoutCdn(Editor)).findComponent(Editor);

    expect(inner.props()).toMatchObject({
      noHighlight: true,
      noKatex: true,
      noMermaid: true,
      noEcharts: true,
    });
  });

  it("passes props, class and listeners through once", async () => {
    const onUpdate = vi.fn();
    const wrapper = mount(withoutCdn(Editor), {
      props: { modelValue: "text", "onUpdate:modelValue": onUpdate },
      attrs: { class: "notes" },
    });

    expect(wrapper.findComponent(Editor).props("modelValue")).toBe("text");
    expect(wrapper.attributes("class")).toBe("notes");
    await wrapper.trigger("click");
    expect(onUpdate).toHaveBeenCalledTimes(1);
    expect(onUpdate).toHaveBeenCalledWith("next");
  });
});
