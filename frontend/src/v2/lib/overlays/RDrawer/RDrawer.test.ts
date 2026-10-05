import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import RDrawer from "./RDrawer.vue";

describe("RDrawer", () => {
  it("is named by its header", async () => {
    const wrapper = mount(RDrawer, {
      props: { modelValue: true },
      slots: { header: "<span>Edit game</span>", content: "<p>Body</p>" },
      global: { stubs: { teleport: true } },
    });
    await nextTick();

    const panel = wrapper.get("[role=dialog]");
    const labelId = panel.attributes("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(wrapper.get(`[id="${labelId}"]`).text()).toBe("Edit game");
    wrapper.unmount();
  });

  it("takes its name from ariaLabel when it has no header", async () => {
    const wrapper = mount(RDrawer, {
      props: { modelValue: true, ariaLabel: "Filters" },
      slots: { content: "<p>Body</p>" },
      global: { stubs: { teleport: true } },
    });
    await nextTick();

    const panel = wrapper.get("[role=dialog]");
    expect(panel.attributes("aria-label")).toBe("Filters");
    expect(panel.attributes("aria-labelledby")).toBeUndefined();
    wrapper.unmount();
  });
});
