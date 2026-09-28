// useRomFileUpload: the one way a v2 tab puts files into a ROM's folder.
//
// The Files tab targets any subfolder and the Media subtabs target the folder
// the scanner maps to their category, but the upload itself is the same:
// confirm the single-file promotion, stream through the chunked upload, ask
// before replacing a file the folder already holds, report the outcome and
// refetch the ROM.
import axios from "axios";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRomSchema } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeUpload from "@/stores/upload";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";

/** The subfolder each Media subtab uploads into. The scanner maps these
 * names to the file category, so the file registers as the tab expects. */
export const ROM_UPLOAD_FOLDERS = {
  manual: "manual",
  walkthrough: "walkthrough",
  screenshots: "screenshots",
  soundtrack: "soundtrack",
} as const;

export type UploadableRom = Pick<
  DetailedRomSchema,
  "id" | "platform_id" | "has_simple_single_file"
>;

export interface RomFileUploadOutcome {
  uploaded: number;
  failed: number;
}

const NOTHING_UPLOADED: RomFileUploadOutcome = { uploaded: 0, failed: 0 };

type Attempt = { file: File; result: PromiseSettledResult<unknown> };

/** The server refuses a name the folder already holds with a 409. */
function isExisting({ result }: Attempt): boolean {
  return (
    result.status === "rejected" &&
    axios.isAxiosError(result.reason) &&
    result.reason.response?.status === 409
  );
}

export function useRomFileUpload() {
  const { t } = useI18n();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const uploadStore = storeUpload();
  const { refetchRom } = useRomSync();
  const alive = useIsAlive();

  const inFlight = ref(0);
  const uploading = computed(() => inFlight.value > 0);

  function failureMessage(name: string, reason: unknown): string {
    const status = axios.isAxiosError(reason)
      ? reason.response?.status
      : undefined;
    if (status === 409) return t("rom.upload-file-exists", { name });
    const error = errorMessage(reason);
    if (status === 400) return t("rom.upload-file-rejected", { name, error });
    return t("rom.upload-file-failed", { name, error });
  }

  /** Upload `files` into `folder` inside the ROM ("" for its root). A lone
   * file ROM is promoted to a folder first, after the user agrees. */
  async function uploadFiles(
    rom: UploadableRom,
    folder: string,
    files: File[],
  ): Promise<RomFileUploadOutcome> {
    if (files.length === 0) return NOTHING_UPLOADED;
    if (rom.has_simple_single_file) {
      const ok = await confirm({
        title: t("rom.convert-to-folder-title"),
        body: t("rom.convert-to-folder-body"),
        tone: "warning",
      });
      if (!ok) return NOTHING_UPLOADED;
    }

    inFlight.value += 1;
    try {
      const send = async (batch: File[], overwrite = false) => {
        const results = await romApi.uploadRoms({
          platformId: rom.platform_id,
          romId: rom.id,
          folder,
          filesToUpload: batch,
          ...(overwrite && { overwrite }),
        });
        return batch.map((file, i) => ({ file, result: results[i] }));
      };

      let attempts = await send(files);
      const existing = attempts.filter(isExisting);
      if (existing.length > 0) {
        attempts = attempts.filter((attempt) => !isExisting(attempt));
        const names = existing.map(({ file }) => file.name).join(", ");
        const ok = await confirm({
          title: t("rom.upload-overwrite-title", existing.length, {
            named: { n: existing.length },
          }),
          body: t("rom.upload-overwrite-body", existing.length, {
            named: { names },
          }),
          confirmText: t("common.overwrite"),
          tone: "danger",
        });
        if (ok) {
          // The refused entries are still in the toast; the retry re-adds them.
          uploadStore.clearFinished();
          attempts = [
            ...attempts,
            ...(await send(
              existing.map(({ file }) => file),
              true,
            )),
          ];
        }
      }
      if (attempts.length === 0) return NOTHING_UPLOADED;

      const results = attempts.map(({ result }) => result);
      const uploaded = results.filter((r) => r.status === "fulfilled").length;
      const failed = results.length - uploaded;
      if (uploaded > 0) {
        snackbar.success(
          failed
            ? t("rom.files-uploaded-with-failed", uploaded, {
                named: { n: uploaded, failed },
              })
            : t("rom.files-uploaded-n", uploaded, { named: { n: uploaded } }),
          { icon: "mdi-check-bold" },
        );
      } else {
        snackbar.warning(t("rom.no-files-uploaded"), {
          icon: "mdi-close-circle",
        });
      }
      const firstFailed = attempts.find(
        ({ result }) => result.status === "rejected",
      );
      if (firstFailed) {
        const rejected = firstFailed.result as PromiseRejectedResult;
        snackbar.error(failureMessage(firstFailed.file.name, rejected.reason));
      }
      if (failed === 0) uploadStore.reset();
      if (alive.value && uploaded > 0) await refetchRom(rom.id);
      return { uploaded, failed };
    } finally {
      inFlight.value -= 1;
    }
  }

  return { uploading, uploadFiles };
}
