import type {
  AppriseServiceSchema,
  NotificationChannelSchema,
} from "@/__generated__";

export function makeChannel(
  overrides: Partial<NotificationChannelSchema> = {},
): NotificationChannelSchema {
  return {
    id: 1,
    type: "apprise",
    name: "Discord",
    enabled: true,
    min_level: "info",
    topics: null,
    target: "discord://1...0/a...p/",
    service: "discord",
    service_name: "Discord",
    fields: {},
    stored_secrets: ["webhook_id", "webhook_token"],
    has_secret: false,
    confirmed: true,
    last_delivered_at: null,
    last_error: null,
    consecutive_failures: 0,
    created_at: "2026-09-23T12:00:00+00:00",
    ...overrides,
  };
}

export function makeAppriseService(
  overrides: Partial<AppriseServiceSchema> = {},
): AppriseServiceSchema {
  const field = {
    required: false,
    private: false,
    advanced: false,
    default: null,
    values: null,
    min: null,
    max: null,
  };
  return {
    id: "ntfy",
    name: "ntfy",
    setup_url: "https://appriseit.com/services/ntfy/",
    fields: [
      {
        ...field,
        key: "schema",
        label: "Schema",
        type: "choice",
        required: true,
        default: "ntfys",
        values: ["ntfy", "ntfys"],
      },
      { ...field, key: "host", label: "Hostname", type: "string" },
      {
        ...field,
        key: "port",
        label: "Port",
        type: "int",
        min: 1,
        max: 65535,
      },
      {
        ...field,
        key: "token",
        label: "Token",
        type: "string",
        private: true,
      },
      {
        ...field,
        key: "targets",
        label: "Targets",
        type: "list",
        required: true,
      },
      {
        ...field,
        key: "image",
        label: "Include Image",
        type: "bool",
        advanced: true,
        default: true,
      },
      {
        ...field,
        key: "priority",
        label: "Priority",
        type: "choice",
        advanced: true,
        default: "default",
        values: ["max", "high", "default", "low", "min"],
      },
    ],
    ...overrides,
  };
}
