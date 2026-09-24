import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AssetEditDialog from "./AssetEditDialog.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/locales", () => ({
  default: { global: { t: (key: string) => key } },
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
};
const RForm = { template: `<form><slot /></form>` };
const RTextField = {
  props: {
    modelValue: { type: String, default: "" },
    errorMessages: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue", "focus"],
  template: `<input
    class="name"
    :value="modelValue"
    :data-errors="errorMessages.join('|')"
    @focus="$emit('focus', $event)"
    @input="$emit('update:modelValue', $event.target.value)"
  />`,
};
// Commits one label per click, standing in for the combobox's Enter.
const RComboboxField = {
  props: { modelValue: { type: Array, default: () => [] } },
  emits: ["update:modelValue"],
  template: `<button
    class="labels"
    type="button"
    :data-labels="modelValue.join('|')"
    @click="$emit('update:modelValue', [...modelValue, 'seed 42'])"
  />`,
};
const RSwitch = {
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<input
    class="public"
    type="checkbox"
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
  return mount(AssetEditDialog, {
    props: {
      modelValue: true,
      title: "Edit state",
      fileName: "Pokemon [2026-09-18].state",
      labels: ["100% run"],
      isPublic: false,
      ...props,
    },
    attachTo: document.body,
    global: {
      stubs: { RDialog, RForm, RTextField, RComboboxField, RSwitch, RBtn },
    },
  });
}

describe("AssetEditDialog", () => {
  it("opens with the stem selected, leaving the extension out", async () => {
    const wrapper = mountDialog();
    const input = wrapper.get(".name").element as HTMLInputElement;

    input.focus();
    await wrapper.vm.$nextTick();

    expect(input.selectionStart).toBe(0);
    expect(input.selectionEnd).toBe("Pokemon [2026-09-18]".length);
    wrapper.unmount();
  });

  it("stays disabled until something changes", async () => {
    const wrapper = mountDialog();

    expect(wrapper.get(".save").attributes("disabled")).toBeDefined();
    await wrapper.get(".public").setValue(true);
    expect(wrapper.get(".save").attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });

  it("submits only the fields that changed", async () => {
    const wrapper = mountDialog();

    await wrapper.get(".name").setValue("  Before the boss.state  ");
    await wrapper.get(".labels").trigger("click");
    await wrapper.get(".save").trigger("click");

    expect(wrapper.emitted("submit")).toEqual([
      [{ fileName: "Before the boss.state", labels: ["100% run", "seed 42"] }],
    ]);
    wrapper.unmount();
  });

  it("flags a name the server refused while the field still holds it", async () => {
    const wrapper = mountDialog({ takenName: "Taken.state" });
    const input = wrapper.get(".name");

    await input.setValue("Taken.state");
    expect(input.attributes("data-errors")).toBe("rom.file-name-taken");
    expect(wrapper.get(".save").attributes("disabled")).toBeDefined();

    await input.setValue("Free.state");
    expect(input.attributes("data-errors")).toBe("");
    expect(wrapper.get(".save").attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });

  it("resets an abandoned edit when it opens again", async () => {
    const wrapper = mountDialog();
    await wrapper.get(".name").setValue("half typed");
    await wrapper.get(".public").setValue(true);

    await wrapper.setProps({ modelValue: false });
    await wrapper.setProps({ modelValue: true });

    expect((wrapper.get(".name").element as HTMLInputElement).value).toBe(
      "Pokemon [2026-09-18].state",
    );
    expect((wrapper.get(".public").element as HTMLInputElement).checked).toBe(
      false,
    );
    wrapper.unmount();
  });
});
