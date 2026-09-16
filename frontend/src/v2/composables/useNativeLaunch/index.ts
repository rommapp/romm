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
  "unsupported-platform": "play.native-error-no-emulator",
  "no-emulator-configured": "play.native-error-no-emulator",
  "emulator-not-found": "play.native-error-no-emulator",
  "download-failed": "play.native-error-download",
  "already-running": "play.native-error-running",
  "invalid-request": "play.native-launch-failed",
  "launch-failed": "play.native-launch-failed",
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
      snackbar.success(t("play.native-running", { name }), {
        icon: "mdi-desktop-classic",
      });
      return;
    }

    // A cancel the shell took reaches the frontend as an aborted download, and
    // the store leaves the mark on only for that one failure. So this is the
    // cancellation landing, and the only place it can honestly be reported.
    if (nativeStore.consumeCancelled(state.romId)) {
      snackbar.info(t("play.native-canceled"), {
        icon: "mdi-close-circle-outline",
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
