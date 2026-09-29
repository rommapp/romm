import type { NotificationSchema } from "@/__generated__";

export function makeNotification(
  overrides: Partial<NotificationSchema> = {},
): NotificationSchema {
  return {
    id: 1,
    kind: "custom",
    level: "info",
    title: null,
    body: null,
    link: null,
    icon: null,
    data: {},
    actor: null,
    read_at: null,
    created_at: "2026-09-23T10:00:00+00:00",
    ...overrides,
  };
}
