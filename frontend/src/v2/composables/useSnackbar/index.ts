// useSnackbar — typed convenience wrapper around the global `snackbarShow`
// emitter event. Removes the per-call boilerplate of importing the emitter
// and constructing a SnackbarStatus payload. The actual rendering still
// happens in `Notifications/NotificationHost.vue`, which stacks toasts.
//
// Usage:
//   const snackbar = useSnackbar();
//   snackbar.success("Saved");
//   snackbar.error("Upload failed", { timeout: 6000 });
//
// Tones map to the four canonical kinds the NotificationHost collapses to:
// success | error | warning | info. When v1 dies the emitter payload can
// drop the free-form `color` string and accept the tone directly.
import type { Emitter } from "mitt";
import { inject } from "vue";
import type { Events } from "@/types/emitter";

export type SnackbarTone = "success" | "error" | "warning" | "info";

export interface SnackbarOptions {
  /** Auto-dismiss timeout in ms. Defaults to NotificationHost's 3000ms. */
  timeout?: number;
  /** Override the default icon for the tone. */
  icon?: string;
  /** Stable id — useful when deduplicating repeated notifications. */
  id?: number;
}

const TONE_TO_COLOR: Record<SnackbarTone, string> = {
  success: "success",
  error: "error",
  warning: "warning",
  info: "info",
};

export function useSnackbar() {
  const emitter = inject<Emitter<Events>>("emitter");

  function show(tone: SnackbarTone, msg: string, opts: SnackbarOptions = {}) {
    emitter?.emit("snackbarShow", {
      msg,
      color: TONE_TO_COLOR[tone],
      ...opts,
    });
  }

  return {
    success(msg: string, opts?: SnackbarOptions) {
      show("success", msg, opts);
    },
    error(msg: string, opts?: SnackbarOptions) {
      show("error", msg, opts);
    },
    warning(msg: string, opts?: SnackbarOptions) {
      show("warning", msg, opts);
    },
    info(msg: string, opts?: SnackbarOptions) {
      show("info", msg, opts);
    },
    show,
  };
}
