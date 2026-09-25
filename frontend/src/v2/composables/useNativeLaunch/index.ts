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
import type { LaunchErrorCode, SaveSyncAction } from "@/types/rommNative";
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

/** What each save outcome says. An archival save is the only user-visible
 *  consequence of a conflict, and the one worth interrupting for: the slot holds
 *  newer progress, so the save the emulator just wrote is not the one RomM will
 *  offer next time. */
const SAVE_KEYS: Record<SaveSyncAction, string> = {
  downloaded: "play.native-save-downloaded",
  uploaded: "play.native-save-uploaded",
  archived: "play.native-save-archived",
  failed: "play.native-save-failed",
};

const SAVE_ICONS: Record<SaveSyncAction, string> = {
  downloaded: "mdi-download-outline",
  uploaded: "mdi-upload-outline",
  archived: "mdi-archive-outline",
  failed: "mdi-alert-circle-outline",
};

export function installNativeLaunchFeedback(): void {
  const { t } = useI18n();
  const snackbar = useSnackbar();
  const nativeStore = useNativeStore();

  nativeStore.install();

  const unsubscribe = onNativeLaunchState((state) => {
    const name = nativeStore.nameFor(state.romId);

    // Not a launch state, and handled before the two that end a launch: the
    // emulator has already exited by the time a save moves, so this arrives on a
    // launch the page is finished with.
    if (state.status === "sync") {
      const outcome = state.sync;
      if (!outcome) return;
      if (outcome.detail) {
        console.error("[native] Save sync failed:", outcome.detail);
      }
      const message = t(SAVE_KEYS[outcome.action], { name });
      const icon = SAVE_ICONS[outcome.action];
      if (outcome.action === "failed") {
        snackbar.error(message, { icon });
      } else if (outcome.action === "archived") {
        snackbar.warning(message, { icon });
      } else {
        snackbar.success(message, { icon });
      }
      return;
    }

    if (state.status !== "running" && state.status !== "failed") return;

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
