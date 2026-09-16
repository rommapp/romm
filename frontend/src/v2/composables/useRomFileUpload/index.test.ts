import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeUpload from "@/stores/upload";
import { ROM_UPLOAD_FOLDERS, useRomFileUpload } from "./index";

const { uploadRoms, refetchRom, confirmFn, snackbar } = vi.hoisted(() => ({
  uploadRoms: vi.fn(),
  refetchRom: vi.fn(),
  confirmFn: vi.fn(),
  snackbar: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/services/api/rom", () => ({
  default: { uploadRoms },
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmFn,
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => snackbar,
}));

const folderRom = { id: 1, platform_id: 7, has_simple_single_file: false };
const singleFileRom = { ...folderRom, has_simple_single_file: true };
const files = [new File(["x"], "track.mp3")];

describe("useRomFileUpload", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    uploadRoms.mockResolvedValue([{ status: "fulfilled", value: null }]);
    confirmFn.mockResolvedValue(true);
  });

  it("uploads into the folder, reports and refetches the rom", async () => {
    const { uploadFiles } = useRomFileUpload();

    const outcome = await uploadFiles(
      folderRom,
      ROM_UPLOAD_FOLDERS.soundtrack,
      files,
    );

    expect(outcome).toEqual({ uploaded: 1, failed: 0 });
    expect(uploadRoms).toHaveBeenCalledWith({
      platformId: 7,
      romId: 1,
      folder: "soundtrack",
      filesToUpload: files,
    });
    expect(confirmFn).not.toHaveBeenCalled();
    expect(snackbar.success).toHaveBeenCalledWith(
      "rom.files-uploaded-n",
      expect.anything(),
    );
    expect(refetchRom).toHaveBeenCalledWith(1);
  });

  it("asks before promoting a single-file rom and respects a no", async () => {
    confirmFn.mockResolvedValue(false);
    const { uploadFiles } = useRomFileUpload();

    const outcome = await uploadFiles(singleFileRom, "", files);

    expect(outcome).toEqual({ uploaded: 0, failed: 0 });
    expect(confirmFn).toHaveBeenCalledWith(
      expect.objectContaining({ tone: "warning" }),
    );
    expect(uploadRoms).not.toHaveBeenCalled();
  });

  it("explains a duplicate and keeps the failed entry in the upload toast", async () => {
    uploadRoms.mockResolvedValue([
      {
        status: "rejected",
        reason: { isAxiosError: true, response: { status: 409 } },
      },
    ]);
    const uploadStore = storeUpload();
    uploadStore.start("track.mp3");
    const { uploadFiles } = useRomFileUpload();

    const outcome = await uploadFiles(folderRom, "soundtrack", files);

    expect(outcome).toEqual({ uploaded: 0, failed: 1 });
    expect(snackbar.error).toHaveBeenCalledWith("rom.upload-file-exists");
    expect(snackbar.warning).toHaveBeenCalledWith(
      "rom.no-files-uploaded",
      expect.anything(),
    );
    expect(refetchRom).not.toHaveBeenCalled();
    expect(uploadStore.files).toHaveLength(1);
  });

  it("tracks in-flight uploads", async () => {
    let release: (() => void) | undefined;
    uploadRoms.mockImplementationOnce(
      () => new Promise((resolve) => (release = () => resolve([]))),
    );
    const { uploading, uploadFiles } = useRomFileUpload();

    const pending = uploadFiles(folderRom, "", files);
    expect(uploading.value).toBe(true);

    release?.();
    await pending;
    expect(uploading.value).toBe(false);
  });
});
