// What a notification channel can pick from, shared by its list and its dialog.
import type {
  NotificationChannelSchema,
  NotificationLevel,
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

// Info and success both mean nothing needs doing, so the lowest bar is info.
export const CHANNEL_LEVELS: NotificationLevel[] = ["info", "warning", "error"];

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
