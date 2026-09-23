// What a notification channel can pick from, shared by its list and its dialog.
import type {
  NotificationChannelMinLevel,
  NotificationChannelSchema,
  NotificationTopic,
  WebhookFormat,
} from "@/__generated__";

export const CHANNEL_TOPICS: NotificationTopic[] = [
  "scans",
  "tasks",
  "streaming",
  "account",
  "custom",
];

export const CHANNEL_LEVELS: NotificationChannelMinLevel[] = [
  "info",
  "warning",
  "error",
];

// Mirror the limits in backend/models/notification_channel.py.
export const NOTIFICATION_CHANNEL_NAME_MAX_LENGTH = 100;
export const NOTIFICATION_CHANNEL_URL_MAX_LENGTH = 2000;
export const NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH = 255;
export const NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH = 320;
export const NOTIFICATION_CHANNEL_CODE_MAX_LENGTH = 16;

export const FORMAT_ICONS: Record<WebhookFormat, string> = {
  json: "mdi-webhook",
  discord: "mdi-forum-outline",
  ntfy: "mdi-bell-ring-outline",
};

export const EMAIL_ICON = "mdi-email-outline";

export function channelIcon(
  channel: Pick<NotificationChannelSchema, "type" | "format">,
): string {
  return channel.type === "email"
    ? EMAIL_ICON
    : FORMAT_ICONS[channel.format ?? "json"];
}
