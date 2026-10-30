// usePackUpload (romm-themeable): Branding's pack upload. Checks the file before sending it, asks
// before replacing an installed pack, and keeps the server's reasons when it refuses one.
import { isAxiosError } from "axios";
import { ref, toValue, type MaybeRefOrGetter } from "vue";
import { useI18n } from "vue-i18n";
import themeableApi, {
  type BrandingStatus,
  type PackClash,
  type PackProblems,
} from "@/services/api/themeable";

export const PACK_EXTENSION = ".zip";
const MB = 1024 * 1024;

export function usePackUpload(
  maxBytes: MaybeRefOrGetter<number>,
  confirmReplace: (clash: PackClash) => Promise<boolean>,
) {
  const { t } = useI18n();
  const uploading = ref(false);
  const error = ref<string | null>(null);
  const problems = ref<string[]>([]);

  function refuse(message: string, list: string[] = []): null {
    error.value = message;
    problems.value = list;
    return null;
  }

  async function send(
    file: File,
    replace: boolean,
  ): Promise<BrandingStatus | null> {
    try {
      const { data } = await themeableApi.uploadPack(file, replace);
      return data.ok ? data : refuse(data.error ?? t("branding.upload-failed"));
    } catch (err) {
      const code = isAxiosError(err) ? err.response?.status : undefined;
      const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
      if (code === 409 && !replace) {
        const clash = detail as PackClash;
        return (await confirmReplace(clash)) ? send(file, true) : null;
      }
      if (code === 422 && detail?.problems) {
        const refused = detail as PackProblems;
        return refuse(refused.message, refused.problems);
      }
      if (code === 413) {
        return refuse(
          t("branding.upload-too-large", {
            mb: Math.floor(toValue(maxBytes) / MB),
          }),
        );
      }
      console.error("[branding] Could not upload the pack:", err);
      return refuse(t("branding.upload-failed"));
    }
  }

  /** Uploads one pack; returns the new status, or null when it was refused or not confirmed. */
  async function upload(file: File): Promise<BrandingStatus | null> {
    error.value = null;
    problems.value = [];
    if (!file.name.toLowerCase().endsWith(PACK_EXTENSION)) {
      return refuse(t("branding.upload-not-zip"));
    }
    if (file.size > toValue(maxBytes)) {
      return refuse(
        t("branding.upload-too-large", {
          mb: Math.floor(toValue(maxBytes) / MB),
        }),
      );
    }
    uploading.value = true;
    try {
      return await send(file, false);
    } finally {
      uploading.value = false;
    }
  }

  return { upload, uploading, error, problems };
}
