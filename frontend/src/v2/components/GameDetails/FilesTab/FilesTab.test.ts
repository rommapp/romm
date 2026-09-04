import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetailedRomSchema, RomFileSchema } from "@/__generated__";
import FilesTab from "./FilesTab.vue";

const { uploadRoms, getRom, confirmFn, snackbar, routeQuery, grants } =
  vi.hoisted(() => ({
    uploadRoms: vi.fn(),
    getRom: vi.fn(),
    confirmFn: vi.fn(),
    snackbar: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    routeQuery: { subtab: undefined as string | undefined },
    grants: { upload: true, delete: false },
  }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ query: routeQuery, path: "/rom/1", params: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));
vi.mock("@/services/api/rom", () => ({
  default: { uploadRoms, getRom, deleteRomFile: vi.fn() },
}));
vi.mock("@/v2/composables/useCan", async () => {
  const { computed } = await import("vue");
  return {
    useCan: (action: string) =>
      computed(() => (action === "rom.upload" ? grants.upload : grants.delete)),
  };
});
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmFn,
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ syncCachedRom: vi.fn() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => snackbar,
}));

const ROM_PATH = "n64/roms/Game";

function file(id: number, rel: string): RomFileSchema {
  const slash = rel.lastIndexOf("/");
  return {
    id,
    rom_id: 1,
    file_name: slash < 0 ? rel : rel.slice(slash + 1),
    file_path: slash < 0 ? ROM_PATH : `${ROM_PATH}/${rel.slice(0, slash)}`,
    full_path: `${ROM_PATH}/${rel}`,
    file_size_bytes: 10,
    is_top_level: slash < 0,
    category: null,
  } as RomFileSchema;
}

function rom(overrides: Partial<DetailedRomSchema> = {}): DetailedRomSchema {
  return {
    id: 1,
    platform_id: 7,
    fs_name: "Game",
    full_path: ROM_PATH,
    has_simple_single_file: false,
    fs_size_bytes: 20,
    files: [file(1, "game.n64"), file(2, "hack/patched.n64")],
    ...overrides,
  } as DetailedRomSchema;
}

const UploadFilesDialogStub = {
  name: "UploadFilesDialog",
  props: ["modelValue"],
  emits: ["submit", "update:modelValue"],
  template: `<div class="dialog" :data-open="String(modelValue)" />`,
};

function mountTab(r = rom()) {
  return mount(FilesTab, {
    props: { rom: r },
    global: {
      stubs: {
        FileRow: true,
        FilesSummary: true,
        RCheckbox: true,
        REmptyState: true,
        RIcon: true,
        RTooltip: {
          template: `<div><slot name="activator" :props="{}" /></div>`,
        },
        RBtn: {
          props: ["disabled", "icon"],
          emits: ["click"],
          template: `<button class="btn" :data-icon="icon" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
        },
        UploadFilesDialog: UploadFilesDialogStub,
      },
    },
  });
}

function uploadButton(wrapper: ReturnType<typeof mountTab>) {
  return wrapper
    .findAll("button.btn")
    .find((b) => b.text() === "common.upload");
}

async function pickFile(wrapper: ReturnType<typeof mountTab>, name: string) {
  const input = wrapper.get("input[type=file]");
  Object.defineProperty(input.element, "files", {
    value: [new File(["x"], name)],
    configurable: true,
  });
  await input.trigger("change");
  await flushPromises();
}

describe("FilesTab uploads", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    routeQuery.subtab = undefined;
    grants.upload = true;
    uploadRoms.mockResolvedValue([{ status: "fulfilled", value: null }]);
    getRom.mockResolvedValue({ data: rom() });
    confirmFn.mockResolvedValue(true);
  });

  it("hides the upload controls without the upload grant", () => {
    grants.upload = false;
    const wrapper = mountTab();

    expect(uploadButton(wrapper)).toBeUndefined();
  });

  it("sends files straight into the active folder", async () => {
    routeQuery.subtab = "hack";
    const click = vi.spyOn(HTMLInputElement.prototype, "click");
    const wrapper = mountTab();

    await uploadButton(wrapper)!.trigger("click");
    expect(click).toHaveBeenCalled();
    await pickFile(wrapper, "fix.ips");

    expect(uploadRoms).toHaveBeenCalledWith({
      platformId: 7,
      romId: 1,
      folder: "hack",
      filesToUpload: [expect.objectContaining({ name: "fix.ips" })],
    });
    expect(getRom).toHaveBeenCalledWith({ romId: 1 });
    expect(snackbar.success).toHaveBeenCalledWith(
      "rom.files-uploaded-n",
      expect.anything(),
    );
    expect(confirmFn).not.toHaveBeenCalled();
  });

  it("targets the rom root from the Root subtab", async () => {
    routeQuery.subtab = "__root__";
    const wrapper = mountTab();

    await pickFile(wrapper, "readme.txt");

    expect(uploadRoms).toHaveBeenCalledWith(
      expect.objectContaining({ folder: "" }),
    );
  });

  it("asks for a destination from All files", async () => {
    const wrapper = mountTab();

    await uploadButton(wrapper)!.trigger("click");
    expect(wrapper.get(".dialog").attributes("data-open")).toBe("true");

    const dialog = wrapper.findComponent(UploadFilesDialogStub);
    dialog.vm.$emit("submit", {
      folder: "cheats",
      files: [new File(["x"], "codes.cht")],
    });
    await flushPromises();

    expect(wrapper.get(".dialog").attributes("data-open")).toBe("false");
    expect(uploadRoms).toHaveBeenCalledWith(
      expect.objectContaining({ folder: "cheats" }),
    );
  });

  it("confirms before converting a single-file rom, and respects a no", async () => {
    routeQuery.subtab = "__root__";
    confirmFn.mockResolvedValue(false);
    const wrapper = mountTab(
      rom({ has_simple_single_file: true, files: [file(1, "game.n64")] }),
    );

    await pickFile(wrapper, "notes.txt");

    expect(confirmFn).toHaveBeenCalledWith(
      expect.objectContaining({ tone: "warning" }),
    );
    expect(uploadRoms).not.toHaveBeenCalled();
  });

  it("explains a duplicate file and skips the refetch", async () => {
    routeQuery.subtab = "hack";
    uploadRoms.mockResolvedValue([
      {
        status: "rejected",
        reason: { isAxiosError: true, response: { status: 409 } },
      },
    ]);
    const wrapper = mountTab();

    await pickFile(wrapper, "patched.n64");

    expect(snackbar.error).toHaveBeenCalledWith("rom.upload-file-exists");
    expect(snackbar.warning).toHaveBeenCalledWith(
      "rom.no-files-uploaded",
      expect.anything(),
    );
    expect(getRom).not.toHaveBeenCalled();
  });
});
