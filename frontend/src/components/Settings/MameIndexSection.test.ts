/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import mameApi from "@/services/api/mame";
import MameIndexSection from "./MameIndexSection.vue";

vi.mock("vue-i18n");

vi.mock("@/services/api/mame", () => ({
  default: {
    getIndexStatus: vi.fn(),
    uploadIndex: vi.fn(),
    updateIndex: vi.fn(),
  },
}));

vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/lib", () => ({
  RBtn: defineComponent({
    props: { disabled: { type: Boolean, default: false } },
    emits: ["click"],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  }),
  RTextField: defineComponent({
    props: { modelValue: { type: String, default: "" } },
    emits: ["update:modelValue"],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  }),
}));

vi.mock("@/components/Settings/SettingsSection.vue", () => ({
  default: defineComponent({ template: "<section><slot /></section>" }),
}));

const status = vi.mocked(mameApi.getIndexStatus);

describe("MameIndexSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("says when no index is loaded", async () => {
    status.mockResolvedValue({ loaded: false, info: null, updating: false });
    const wrapper = mount(MameIndexSection);
    await flushPromises();
    expect(wrapper.find("[data-testid=mame-index-status]").text()).toBe(
      "settings.mame-index-none",
    );
  });

  it("shows the loaded build", async () => {
    status.mockResolvedValue({
      loaded: true,
      info: {
        build: "0.289 (mame0289)",
        sets: 48000,
        source: "upload",
        updated_at: "2026-11-19T10:00:00+00:00",
      },
      updating: false,
    });
    const wrapper = mount(MameIndexSection);
    await flushPromises();
    const text = wrapper.find("[data-testid=mame-index-status]").text();
    expect(text).toContain("settings.mame-index-loaded");
    expect(text).toContain("0.289 (mame0289)");
  });

  it("queues the latest release", async () => {
    status.mockResolvedValue({ loaded: false, info: null, updating: false });
    const wrapper = mount(MameIndexSection);
    await flushPromises();
    await wrapper.findAll("button")[0]!.trigger("click");
    await flushPromises();
    expect(mameApi.updateIndex).toHaveBeenCalledWith();
  });

  it("queues a given URL", async () => {
    status.mockResolvedValue({ loaded: false, info: null, updating: false });
    const wrapper = mount(MameIndexSection);
    await flushPromises();
    const url = "https://example.com/mame0289lx.zip";
    await wrapper.find("input:not([type=file])").setValue(url);
    const buttons = wrapper.findAll("button");
    await buttons[buttons.length - 1]!.trigger("click");
    await flushPromises();
    expect(mameApi.updateIndex).toHaveBeenCalledWith(url);
  });
});
