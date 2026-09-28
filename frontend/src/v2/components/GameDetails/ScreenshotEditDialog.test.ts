import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ScreenshotEditDialog from "./ScreenshotEditDialog.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
};
const RForm = { template: `<form><slot /></form>` };
const RSwitch = {
  props: {
    modelValue: { type: Boolean, default: false },
    ariaLabel: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  template: `<input
    class="public"
    type="checkbox"
    :data-label="ariaLabel"
    :checked="modelValue"
    @change="$emit('update:modelValue', $event.target.checked)"
  />`,
};
const RBtn = {
  props: { disabled: { type: Boolean, default: false } },
  emits: ["click"],
  template: `<button class="save" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
};

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(ScreenshotEditDialog, {
    props: { modelValue: true, isPublic: false, ...props },
    global: { stubs: { RDialog, RForm, RSwitch, RBtn } },
  });
}

describe("ScreenshotEditDialog", () => {
  it("saves only a changed visibility", async () => {
    const wrapper = mountDialog();
    const save = wrapper.get(".save");
    expect(save.attributes("disabled")).toBeDefined();
    expect(wrapper.get(".public").attributes("data-label")).toBe(
      "common.private",
    );

    await wrapper.get(".public").setValue(true);
    expect(wrapper.get(".public").attributes("data-label")).toBe(
      "common.public",
    );
    await save.trigger("click");

    expect(wrapper.emitted("submit")).toEqual([[true]]);
  });

  it("resets an abandoned change when it opens again", async () => {
    const wrapper = mountDialog({ isPublic: true });
    await wrapper.get(".public").setValue(false);

    await wrapper.setProps({ modelValue: false });
    await wrapper.setProps({ modelValue: true });

    expect((wrapper.get(".public").element as HTMLInputElement).checked).toBe(
      true,
    );
  });
});
