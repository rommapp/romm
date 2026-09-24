// RomM's own kinds are translated from their values, so they read in the
// language of whoever opens them; any other kind brings its own title and body.
import type { RouteLocationRaw } from "vue-router";
import type { NotificationKind, NotificationSchema } from "@/__generated__";
import i18n from "@/locales";
import { ROUTES } from "@/plugins/routeNames";
import { TONE_ICONS } from "@/v2/composables/useSnackbar";

interface NotificationView {
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

// Mirror the columns in backend/models/notification.py.
export const NOTIFICATION_TITLE_MAX_LENGTH = 255;
export const NOTIFICATION_BODY_MAX_LENGTH = 1000;
export const NOTIFICATION_LINK_MAX_LENGTH = 1000;

/** Whether a link stays inside RomM, by the rule the server enforces. */
export function isInAppPath(link: string): boolean {
  return (
    link.startsWith("/") &&
    !link.startsWith("//") &&
    !link.includes("\\") &&
    !/\s/.test(link)
  );
}

function ownContent(notification: NotificationSchema): NotificationView {
  return {
    icon: notification.icon ?? TONE_ICONS[notification.level],
    title: notification.title ?? t("notifications.unknown"),
    body: notification.body,
    to:
      notification.link && isInAppPath(notification.link)
        ? notification.link
        : null,
    toast: true,
  };
}

function taskView(
  key: string,
  data: NotificationData,
  body: string | null,
): NotificationView {
  return {
    icon: "mdi-pulse",
    title: t(key, { task: text(data.title) ?? "" }),
    body,
    to: { name: ROUTES.ADMINISTRATION },
    toast: true,
  };
}

const DESCRIBERS: Record<
  Exclude<NotificationKind, "custom">,
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
  task_completed: (data) =>
    taskView("notifications.task-completed", data, null),
  task_failed: (data) =>
    taskView("notifications.task-failed", data, text(data.error)),
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
  channel_disabled: (data) => ({
    icon: "mdi-send-variant-outline",
    title: t("notifications.channel-disabled", { name: text(data.name) ?? "" }),
    body: text(data.error),
    to: { name: ROUTES.NOTIFICATIONS, query: { tab: "channels" } },
    toast: true,
  }),
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

function isTranslatedKind(kind: string): kind is keyof typeof DESCRIBERS {
  return Object.hasOwn(DESCRIBERS, kind);
}

export function describeNotification(
  notification: NotificationSchema,
): NotificationView {
  return isTranslatedKind(notification.kind)
    ? DESCRIBERS[notification.kind](notification.data)
    : ownContent(notification);
}
