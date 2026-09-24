import type { NotificationChannelSchema } from "@/__generated__";

export function makeChannel(
  overrides: Partial<NotificationChannelSchema> = {},
): NotificationChannelSchema {
  return {
    id: 1,
    type: "webhook",
    name: "Discord",
    enabled: true,
    min_level: "info",
    topics: null,
    target: "https://discord.com/…oken",
    format: "discord",
    has_secret: false,
    confirmed: true,
    last_delivered_at: null,
    last_error: null,
    consecutive_failures: 0,
    created_at: "2026-09-23T12:00:00+00:00",
    ...overrides,
  };
}
