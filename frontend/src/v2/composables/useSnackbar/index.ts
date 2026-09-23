// useSnackbar — typed convenience wrapper around the global `snackbarShow`
// emitter event. Removes the per-call boilerplate of importing the emitter
// and constructing a SnackbarStatus payload. The actual rendering still
// happens in `Notifications/NotificationHost.vue`, which stacks toasts.
//
// Usage:
//   const snackbar = useSnackbar();
//   snackbar.success("Saved");
//   snackbar.error("Upload failed", { timeout: 6000 });
//   snackbar.success("Upload finished", { persist: { link: "/rom/12" } });
//
// Tones map to the four canonical kinds the NotificationHost collapses to:
// success | error | warning | info. When v1 dies the emitter payload can
// drop the free-form `color` string and accept the tone directly.
import type { Emitter } from "mitt";
import { inject } from "vue";
import type { Events } from "@/types/emitter";
import storeNotificationInbox from "@/v2/stores/notificationInbox";

export type SnackbarTone = "success" | "error" | "warning" | "info";

export interface SnackbarOptions {
  /** Auto-dismiss timeout in ms. Defaults to NotificationHost's 3000ms. */
  timeout?: number;
  /** Override the default icon for the tone. */
  icon?: string;
  /** Stable id — useful when deduplicating repeated notifications. */
  id?: number;
  /** Artwork shown in place of the icon, e.g. the cover of the game it concerns. */
  image?: string | null;
  /** Also keeps it in the user's notifications, optionally with a detail
   *  line and an in-app link. */
  persist?: boolean | { body?: string; link?: string };
}

const TONE_TO_COLOR: Record<SnackbarTone, string> = {
  success: "success",
  error: "error",
  warning: "warning",
  info: "info",
};

export function useSnackbar() {
  const emitter = inject<Emitter<Events>>("emitter");

  function toast(
    tone: SnackbarTone,
    msg: string,
    { persist: _, ...opts }: SnackbarOptions,
  ) {
    emitter?.emit("snackbarShow", {
      msg,
      color: TONE_TO_COLOR[tone],
      ...opts,
    });
  }

  async function persist(
    tone: SnackbarTone,
    msg: string,
    opts: SnackbarOptions,
  ) {
    const extra = typeof opts.persist === "object" ? opts.persist : {};
    try {
      const inbox = storeNotificationInbox();
      const notification = await inbox.send({
        level: tone,
        title: msg,
        body: extra.body,
        link: extra.link,
        icon: opts.icon,
      });
      // The socket push can arrive first, and it shows the toast itself.
      if (!inbox.receive(notification)) return;
    } catch (error) {
      console.error("Could not keep the notification:", error);
    }
    toast(tone, msg, opts);
  }

  function show(tone: SnackbarTone, msg: string, opts: SnackbarOptions = {}) {
    if (opts.persist) void persist(tone, msg, opts);
    else toast(tone, msg, opts);
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
