// installNativeLaunchFeedback — the app-level voice of the desktop shell's
// launches. Mounted once from AppLayout, next to the other install* hooks.
//
// Progress lives on the native Play button itself (`nativeActionLabel` in
// useGameActions); this speaks only at the two endings worth a toast. The
// subscription is app-wide because a per-ROM one would mean a listener, and a
// toast, per card in a virtualised gallery.
import { onScopeDispose } from "vue";
import { useI18n } from "vue-i18n";
import { onNativeLaunchState } from "@/services/native";
import { useNativeStore } from "@/stores/native";
import type { LaunchErrorCode } from "@/types/rommNative";
import { useSnackbar } from "@/v2/composables/useSnackbar";

/** Several codes share one message: from the user's side a platform with no
 *  emulator, none configured, and one gone missing are the same problem. What
 *  tells them apart is the shell's `detail`, which is English. */
const ERROR_KEYS: Record<LaunchErrorCode, string> = {
  "unsupported-platform": "rom.native-error-no-emulator",
  "no-emulator-configured": "rom.native-error-no-emulator",
  "emulator-not-found": "rom.native-error-no-emulator",
  "download-failed": "rom.native-error-download",
  "already-running": "rom.native-error-running",
  "invalid-request": "rom.native-launch-failed",
  "launch-failed": "rom.native-launch-failed",
};

export function installNativeLaunchFeedback(): void {
  const { t } = useI18n();
  const snackbar = useSnackbar();
  const nativeStore = useNativeStore();

  nativeStore.install();

  const unsubscribe = onNativeLaunchState((state) => {
    if (state.status !== "running" && state.status !== "failed") return;
    const name = nativeStore.nameFor(state.romId);

    if (state.status === "running") {
      snackbar.success(t("rom.native-running", { name }), {
        icon: "mdi-monitor-play",
      });
      return;
    }

    if (state.error?.message) {
      console.error("[native] Launch failed:", state.error.message);
    }
    snackbar.error(
      t(ERROR_KEYS[state.error?.code ?? "launch-failed"], { name }),
      {
        icon: "mdi-alert-circle-outline",
      },
    );
  });

  onScopeDispose(unsubscribe);
}
