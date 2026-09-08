import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import ManualUploadTargetDialog from "./ManualUploadTargetDialog.vue";

type UploadArgs = { romId: number; filesToUpload: File[] };

const { uploadManuals, uploadManualFiles, getRom } = vi.hoisted(() => ({
  uploadManuals: vi.fn((_args: UploadArgs) => Promise.resolve([])),
  uploadManualFiles: vi.fn((_args: UploadArgs) => Promise.resolve([])),
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

function manualFile(): NonNullable<DetailedRom["files"]>[number] {
  return {
    id: 1,
    rom_id: 7,
    file_name: "guide.pdf",
    file_path: "switch/roms/Game",
    file_size_bytes: 1024,
    full_path: "switch/roms/Game/manual/guide.pdf",
    is_top_level: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    last_modified: "2026-01-01T00:00:00Z",
    crc_hash: null,
    md5_hash: null,
    sha1_hash: null,
    ra_hash: null,
    chd_sha1_hash: null,
    archive_members: null,
    category: "manual",
  };
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
    const wrapper = await upload(rom({ files: [manualFile()] }));

    expect(uploadManualFiles).toHaveBeenCalledOnce();
    expect(uploadManuals).not.toHaveBeenCalled();
    expect(wrapper.find("[data-test-dialog]").exists()).toBe(false);
  });

  it("uploads both manuals when a second is dropped mid-upload", async () => {
    let release: (() => void) | undefined;
    uploadManuals.mockImplementationOnce(
      () => new Promise<never[]>((resolve) => (release = () => resolve([]))),
    );

    const emitter = mitt<Events>();
    mountDialog(emitter);
    const payload = (name: string) => ({
      rom: rom({ has_simple_single_file: true }),
      files: [new File(["x"], name)],
    });

    emitter.emit("showManualUploadTargetDialog", payload("first.pdf"));
    await flushPromises();
    emitter.emit("showManualUploadTargetDialog", payload("second.pdf"));
    await flushPromises();

    expect(uploadManuals).toHaveBeenCalledOnce();

    release?.();
    await flushPromises();

    expect(uploadManuals).toHaveBeenCalledTimes(2);
    const secondCall = uploadManuals.mock.calls[1];
    if (!secondCall) throw new Error("the queued upload never ran");
    expect(secondCall[0].filesToUpload[0]?.name).toBe("second.pdf");
  });

  it("asks when a folder ROM has no manual yet", async () => {
    const wrapper = await upload(rom());

    expect(uploadManuals).not.toHaveBeenCalled();
    expect(uploadManualFiles).not.toHaveBeenCalled();
    expect(wrapper.find("[data-test-dialog]").exists()).toBe(true);
  });
});
