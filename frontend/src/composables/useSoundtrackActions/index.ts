// Confirm + delete + notify for one soundtrack track, shared by both hosts
// of the soundtrack panel (the game's media tab and the jukebox).
import { useI18n } from "vue-i18n";
import { useConfirm } from "@/composables/useConfirm";
import { useSnackbar } from "@/composables/useSnackbar";
import romApi from "@/services/api/rom";
import { errorMessage } from "@/utils/errorMessage";

export function useSoundtrackActions() {
  const { t } = useI18n();
  const confirm = useConfirm();
  const snackbar = useSnackbar();

  /** Returns true when the track was actually removed. */
  async function deleteTrack(
    romId: number,
    fileId: number,
    name?: string,
  ): Promise<boolean> {
    const ok = await confirm({
      title: t("rom.delete-track-title"),
      body: name
        ? t("rom.delete-track-body-named", { name })
        : t("rom.delete-track-body"),
      confirmText: t("rom.soundtrack-delete-track"),
      tone: "danger",
    });
    if (!ok) return false;

    try {
      await romApi.removeSoundtrack({ romId, fileId });
      snackbar.success(t("rom.soundtrack-removed"), { icon: "mdi-check-bold" });
      return true;
    } catch (error: unknown) {
      snackbar.error(
        t("rom.soundtrack-remove-failed", { error: errorMessage(error) }),
        { icon: "mdi-close-circle" },
      );
      return false;
    }
  }

  return { deleteTrack };
}
