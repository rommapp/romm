import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RChip from "./RChip.vue";

function mountChip(
  text: string,
  widths: { scroll: number; client: number },
  attrs: Record<string, string> = {},
) {
  const wrapper = mount(RChip, { slots: { default: text }, attrs });
  const content = wrapper.get(".r-chip__content").element;
  Object.defineProperty(content, "scrollWidth", { value: widths.scroll });
  Object.defineProperty(content, "clientWidth", { value: widths.client });
  return wrapper;
}

describe("RChip truncation title", () => {
  it("shows the full text as a title when the label is truncated", async () => {
    const wrapper = mountChip("Chinese (Simplified)", {
      scroll: 140,
      client: 80,
    });
    await wrapper.trigger("pointerenter");
    expect(wrapper.attributes("title")).toBe("Chinese (Simplified)");
  });

  it("adds no title when the label fits", async () => {
    const wrapper = mountChip("English", { scroll: 60, client: 60 });
    await wrapper.trigger("pointerenter");
    expect(wrapper.attributes("title")).toBeUndefined();
  });

  it("keeps a title passed by the consumer", async () => {
    const wrapper = mountChip(
      "Chinese (Simplified)",
      { scroll: 140, client: 80 },
      { title: "Language" },
    );
    await wrapper.trigger("pointerenter");
    expect(wrapper.attributes("title")).toBe("Language");
  });
});
