// A stored notification carries its kind and the values behind its text, not
// the text itself, so it reads in the language of whoever opens it.
import type { RouteLocationRaw } from "vue-router";
import type { NotificationKind, NotificationSchema } from "@/__generated__";
import i18n from "@/locales";
import { ROUTES } from "@/plugins/routeNames";

export interface NotificationView {
  icon: string;
  title: string;
  body: string | null;
  to: RouteLocationRaw | null;
  /** False when a live event of the kind's own already shows a toast. */
  toast: boolean;
}

type NotificationData = NotificationSchema["data"];

const t = i18n.global.t;

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

const DESCRIBERS: Record<
  NotificationKind,
  (data: NotificationData) => NotificationView
> = {
  scan_completed: (data) => {
    const newRoms = count(data.new_roms);
    return {
      icon: "mdi-radar",
      title: t("notifications.scan-completed"),
      body:
        newRoms > 0
          ? t("notifications.scan-new-games", newRoms, {
              named: { n: newRoms },
            })
          : t("notifications.scan-no-new-games"),
      to: { name: ROUTES.SCAN },
      toast: false,
    };
  },
  scan_failed: (data) => ({
    icon: "mdi-radar",
    title: t("notifications.scan-failed"),
    body: text(data.error),
    to: { name: ROUTES.SCAN },
    toast: false,
  }),
  task_completed: (data) => ({
    icon: "mdi-pulse",
    title: t("notifications.task-completed", {
      task: text(data.title) ?? text(data.task) ?? "",
    }),
    body: null,
    to: { name: ROUTES.ADMINISTRATION },
    toast: true,
  }),
  task_failed: (data) => ({
    icon: "mdi-pulse",
    title: t("notifications.task-failed", {
      task: text(data.title) ?? text(data.task) ?? "",
    }),
    body: text(data.error),
    to: { name: ROUTES.ADMINISTRATION },
    toast: true,
  }),
  streaming_session_ended: (data) => {
    const game = text(data.rom_name);
    const romId = count(data.rom_id);
    return {
      icon: "mdi-monitor-off",
      title: game
        ? t("notifications.stream-ended", { game })
        : t("notifications.stream-ended-no-game"),
      body: text(data.reason),
      to: romId ? { name: ROUTES.ROM, params: { rom: romId } } : null,
      toast: true,
    };
  },
  role_changed: (data) => {
    const role = text(data.role);
    return {
      icon: "mdi-shield-account-outline",
      title: t("notifications.role-changed", {
        role: role ? t(`settings.role-${role}`) : "",
      }),
      body: null,
      to: null,
      toast: true,
    };
  },
};

function isKnownKind(kind: string): kind is NotificationKind {
  return Object.hasOwn(DESCRIBERS, kind);
}

export function describeNotification(
  notification: NotificationSchema,
): NotificationView {
  if (isKnownKind(notification.kind)) {
    return DESCRIBERS[notification.kind](notification.data);
  }
  return {
    icon: "mdi-bell-outline",
    title: t("notifications.unknown"),
    body: null,
    to: null,
    toast: true,
  };
}
