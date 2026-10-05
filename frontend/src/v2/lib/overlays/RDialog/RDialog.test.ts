import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import RDialog from "./RDialog.vue";

describe("RDialog", () => {
  it("is named by its header", async () => {
    const wrapper = mount(RDialog, {
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
});
