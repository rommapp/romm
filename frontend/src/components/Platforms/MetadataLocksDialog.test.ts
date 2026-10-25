/* eslint-disable vue/one-component-per-file */
import { defineComponent, nextTick } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MetadataLocksDialog from "./MetadataLocksDialog.vue";

const { updateBulkMetadataLocks, success, error } = vi.hoisted(() => ({
  updateBulkMetadataLocks: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/services/api/rom", () => ({
  default: { updateBulkMetadataLocks },
}));
vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error }),
}));

const RDialog = defineComponent({
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
});
const RCheckbox = defineComponent({
  props: {
    modelValue: { type: Boolean, default: false },
    label: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  template: `<label><input type="checkbox" :checked="modelValue" />{{ label }}</label>`,
});
const RSelect = defineComponent({
  props: {
    modelValue: { type: [String, Number, Boolean], default: null },
    items: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue"],
  template: `<div />`,
});
const RBtn = defineComponent({
  emits: ["click"],
  template: `<button @click="$emit('click')"><slot /></button>`,
});

const platforms = [
  { id: 3, display_name: "SNES" },
  { id: 5, display_name: "Game Boy" },
] as never[];

describe("MetadataLocksDialog", () => {
  beforeEach(() => {
    updateBulkMetadataLocks.mockResolvedValue({
      data: { updated: 2, failed: 0 },
    });
    updateBulkMetadataLocks.mockClear();
    success.mockClear();
    error.mockClear();
  });

  it("submits selected fields for the entire library", async () => {
    const wrapper = mount(MetadataLocksDialog, {
      props: { modelValue: true, platforms },
      global: { stubs: { RDialog, RCheckbox, RSelect, RBtn } },
    });
    const name = wrapper
      .findAllComponents(RCheckbox)
      .find((checkbox) => checkbox.props("label") === "common.name");
    expect(name).toBeDefined();
    name!.vm.$emit("update:modelValue", true);
    await nextTick();
    await wrapper.findComponent(RBtn).trigger("click");
    await flushPromises();

    expect(updateBulkMetadataLocks).toHaveBeenCalledWith({
      fields: ["name"],
      locked: true,
      all: true,
    });
    expect(success).toHaveBeenCalledWith("rom.bulk-metadata-lock-result", {
      icon: "mdi-check-bold",
    });
  });

  it("targets a platform when the library-wide scope is disabled", async () => {
    const wrapper = mount(MetadataLocksDialog, {
      props: { modelValue: true, platforms },
      global: { stubs: { RDialog, RCheckbox, RSelect, RBtn } },
    });
    const library = wrapper
      .findAllComponents(RCheckbox)
      .find(
        (checkbox) => checkbox.props("label") === "rom.metadata-lock-library",
      );
    library!.vm.$emit("update:modelValue", false);
    await nextTick();

    const platformSelect = wrapper
      .findAllComponents(RSelect)
      .find((select) => (select.props("items") ?? []).length === 2);
    platformSelect!.vm.$emit("update:modelValue", 3);
    const name = wrapper
      .findAllComponents(RCheckbox)
      .find((checkbox) => checkbox.props("label") === "common.name");
    name!.vm.$emit("update:modelValue", true);
    await nextTick();
    await wrapper.findComponent(RBtn).trigger("click");
    await flushPromises();

    expect(updateBulkMetadataLocks).toHaveBeenCalledWith({
      fields: ["name"],
      locked: true,
      platform_id: 3,
    });
  });
});
