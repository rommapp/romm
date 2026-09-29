import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import MemoryCardDialog from "./MemoryCardDialog.vue";

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
  props: { modelValue: { type: String, default: "" } },
  emits: ["update:modelValue"],
  template: `<input class="name" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
};
const RSwitch = {
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<input class="public" type="checkbox" :checked="modelValue" @change="$emit('update:modelValue', $event.target.checked)" />`,
};
const RBtn = {
  props: { disabled: { type: Boolean, default: false } },
  emits: ["click"],
  template: `<button class="confirm" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
};

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(MemoryCardDialog, {
    props: {
      modelValue: true,
      title: "Edit memory card",
      confirmLabel: "Save",
      ...props,
    },
    global: { stubs: { RDialog, RForm, RTextField, RSwitch, RBtn } },
  });
}

describe("MemoryCardDialog", () => {
  it("opens on the card's name and visibility", () => {
    const wrapper = mountDialog({ initialName: "Main", initialPublic: true });

    expect((wrapper.get(".name").element as HTMLInputElement).value).toBe(
      "Main",
    );
    expect((wrapper.get(".public").element as HTMLInputElement).checked).toBe(
      true,
    );
  });

  it("keeps Save off until the name or the visibility changes", async () => {
    const wrapper = mountDialog({ initialName: "Main" });
    expect(wrapper.get(".confirm").attributes("disabled")).toBeDefined();

    await wrapper.get(".public").setValue(true);
    expect(wrapper.get(".confirm").attributes("disabled")).toBeUndefined();
  });

  it("submits the trimmed name with the visibility", async () => {
    const wrapper = mountDialog();

    await wrapper.get(".name").setValue("  Shared card  ");
    await wrapper.get(".public").setValue(true);
    await wrapper.get(".confirm").trigger("click");

    expect(wrapper.emitted("submit")).toEqual([
      [{ name: "Shared card", isPublic: true }],
    ]);
  });
});
