// What a notification channel can pick from, shared by its list and its dialog.
import type {
  AppriseChannelCreatePayload,
  AppriseFieldSchema,
  AppriseServiceSchema,
  NotificationChannelMinLevel,
  NotificationChannelType,
  NotificationTopic,
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

export const CHANNEL_ICONS: Record<NotificationChannelType, string> = {
  apprise: "mdi-bell-ring-outline",
  webhook: "mdi-webhook",
  email: "mdi-email-outline",
};

export type AppriseFieldValue = AppriseChannelCreatePayload["fields"][string];

// Fields most services share get a translated label; the rest keep Apprise's.
const APPRISE_FIELD_LABELS: Record<string, string> = {
  schema: "notifications.channel-field-schema",
  botname: "notifications.channel-field-botname",
  host: "notifications.channel-field-host",
  port: "notifications.channel-field-port",
  user: "settings.username",
  password: "settings.password",
  token: "notifications.channel-field-token",
  targets: "notifications.channel-field-targets",
  path: "notifications.channel-field-path",
  verify: "notifications.channel-field-verify",
};

/** A field's label: translated when most services share it, Apprise's otherwise. */
export function appriseFieldLabel(
  field: AppriseFieldSchema,
  t: (key: string) => string,
): string {
  const key = APPRISE_FIELD_LABELS[field.key];
  return key ? t(key) : field.label;
}

function isBlank(value: AppriseFieldValue | undefined): boolean {
  return (
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

function emptyValue(field: AppriseFieldSchema): AppriseFieldValue {
  if (field.type === "list") return [];
  if (field.type === "bool") return field.default === true;
  if (field.type === "choice") return String(field.default ?? "");
  return "";
}

/** The form's starting values: the service's defaults, then what the channel has. */
export function initialAppriseValues(
  service: AppriseServiceSchema,
  stored: Record<string, AppriseFieldValue> | null = null,
): Record<string, AppriseFieldValue> {
  return Object.fromEntries(
    service.fields.map((field) => {
      const kept = stored?.[field.key];
      if (kept === undefined) return [field.key, emptyValue(field)];
      return [field.key, typeof kept === "number" ? String(kept) : kept];
    }),
  );
}

/** The filled-in fields as the backend takes them, with a removed secret as "". */
export function appriseFieldsPayload(
  service: AppriseServiceSchema,
  values: Record<string, AppriseFieldValue>,
  removed: string[] = [],
): Record<string, AppriseFieldValue> {
  const payload: Record<string, AppriseFieldValue> = {};
  for (const field of service.fields) {
    const value = values[field.key];
    if (removed.includes(field.key)) payload[field.key] = "";
    else if (isBlank(value)) continue;
    else if (field.type === "int" || field.type === "float") {
      payload[field.key] = Number(value);
    } else payload[field.key] = value;
  }
  return payload;
}
