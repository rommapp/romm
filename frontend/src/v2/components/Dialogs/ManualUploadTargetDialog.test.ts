import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import ManualUploadTargetDialog from "./ManualUploadTargetDialog.vue";

const { uploadManuals, uploadManualFiles, getRom } = vi.hoisted(() => ({
  uploadManuals: vi.fn(() => Promise.resolve([])),
  uploadManualFiles: vi.fn(() => Promise.resolve([])),
  getRom: vi.fn(() => Promise.resolve({ data: {} })),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api/rom", () => ({
  default: { uploadManuals, uploadManualFiles, getRom },
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ syncCachedRom: vi.fn() }),
}));

function rom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 7,
    name: "Game",
    has_simple_single_file: false,
    files: [],
    ...overrides,
  } as DetailedRom;
}

function manualFile() {
  return { id: 1, file_name: "guide.pdf", category: "manual" };
}

function mountDialog(emitter: Emitter<Events>): VueWrapper {
  return mount(ManualUploadTargetDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          template:
            "<div v-if='modelValue' data-test-dialog><slot name='content' /></div>",
        },
        RBtn: true,
        RIcon: true,
      },
    },
  });
}

async function upload(target: DetailedRom): Promise<VueWrapper> {
  const emitter = mitt<Events>();
  const wrapper = mountDialog(emitter);
  emitter.emit("showManualUploadTargetDialog", {
    rom: target,
    files: [new File(["x"], "manual.pdf")],
  });
  await flushPromises();
  return wrapper;
}

describe("ManualUploadTargetDialog", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("sends a single-file ROM's manual to resources without asking", async () => {
    const wrapper = await upload(rom({ has_simple_single_file: true }));

    expect(uploadManuals).toHaveBeenCalledOnce();
    expect(uploadManualFiles).not.toHaveBeenCalled();
    expect(wrapper.find("[data-test-dialog]").exists()).toBe(false);
  });

  it("appends to the ROM folder without asking once it holds a manual", async () => {
    const wrapper = await upload(rom({ files: [manualFile()] } as never));

    expect(uploadManualFiles).toHaveBeenCalledOnce();
    expect(uploadManuals).not.toHaveBeenCalled();
    expect(wrapper.find("[data-test-dialog]").exists()).toBe(false);
  });

  it("asks when a folder ROM has no manual yet", async () => {
    const wrapper = await upload(rom());

    expect(uploadManuals).not.toHaveBeenCalled();
    expect(uploadManualFiles).not.toHaveBeenCalled();
    expect(wrapper.find("[data-test-dialog]").exists()).toBe(true);
  });
});
