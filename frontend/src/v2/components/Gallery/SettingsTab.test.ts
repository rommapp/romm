import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Platform } from "@/stores/platforms";
import SettingsTab from "./SettingsTab.vue";

const { updatePlatform } = vi.hoisted(() => ({
  updatePlatform: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string, fallback?: string) => fallback ?? key }),
}));

vi.mock("@/services/api/platform", () => ({
  default: { updatePlatform },
}));

vi.mock("@/stores/platforms", () => ({
  default: () => ({ update: vi.fn() }),
}));

vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => ({ currentPlatform: null, setCurrentPlatform: vi.fn() }),
}));

vi.mock("@/v2/composables/useCan", () => ({
  useCan: () => ({ value: true }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: vi.fn(), success: vi.fn(), warning: vi.fn() }),
}));

function platform(overrides: Partial<Platform> = {}): Platform {
  return {
    id: 1,
    slug: "fds",
    fs_slug: "fds",
    rom_count: 0,
    name: "Family Computer Disk System",
    igdb_slug: null,
    moby_slug: null,
    hltb_slug: null,
    libretro_slug: null,
    custom_name: "",
    description: null,
    created_at: "",
    updated_at: "",
    fs_size_bytes: 0,
    is_unidentified: false,
    is_identified: true,
    missing_from_fs: false,
    display_name: "Family Computer Disk System",
    firmware_count: 0,
    ...overrides,
  } as Platform;
}

function mountTab(p: Platform) {
  return mount(SettingsTab, {
    props: { platform: p },
    global: {
      stubs: {
        RForm: {
          template: "<form><slot /></form>",
          methods: {
            validate: () => Promise.resolve(true),
          },
        },
        RIcon: true,
        RBtn: { template: "<button><slot /></button>" },
        RTextField: {
          props: ["modelValue"],
          emits: ["update:modelValue"],
          template:
            "<input :value='modelValue' @input=\"$emit('update:modelValue', $event.target.value)\" />",
        },
      },
    },
  });
}

describe("SettingsTab platform save", () => {
  beforeEach(() => {
    updatePlatform.mockClear();
  });

  it("does not stamp custom_name when only the description changed", async () => {
    updatePlatform.mockResolvedValue({ data: platform() });
    const p = platform();
    const wrapper = mountTab(p);

    // Second field is the description.
    const inputs = wrapper.findAll("input");
    await inputs[1].setValue("Aftermarket dumps only");
    await (wrapper.vm as unknown as { save: () => Promise<void> }).save();
    await flushPromises();

    expect(updatePlatform).toHaveBeenCalledTimes(1);
    const arg = updatePlatform.mock.calls[0][0];
    // The untouched name must go back as the stored value (""), not as the
    // display_name fallback, or the platform gains a custom name it never had.
    expect(arg.platform.custom_name).toBe("");
    expect(arg.description).toBe("Aftermarket dumps only");
  });

  it("omits description when only the name changed", async () => {
    updatePlatform.mockResolvedValue({ data: platform() });
    const p = platform({ description: "Existing text" });
    const wrapper = mountTab(p);

    const inputs = wrapper.findAll("input");
    await inputs[0].setValue("FDS (JP only)");
    await (wrapper.vm as unknown as { save: () => Promise<void> }).save();
    await flushPromises();

    const arg = updatePlatform.mock.calls[0][0];
    expect(arg.platform.custom_name).toBe("FDS (JP only)");
    expect(arg.description).toBeUndefined();
  });
});
