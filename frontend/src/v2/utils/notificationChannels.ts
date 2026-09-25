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

// Fields most services share, labelled by RomM; the rest keep Apprise's label.
export const TRANSLATED_APPRISE_FIELDS = new Set([
  "schema",
  "host",
  "port",
  "user",
  "password",
  "token",
  "targets",
  "path",
  "verify",
]);

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

/** What the backend gets: filled-in fields, numbers as numbers, defaults left out. */
export function appriseFieldsPayload(
  service: AppriseServiceSchema,
  values: Record<string, AppriseFieldValue>,
): Record<string, AppriseFieldValue> {
  const payload: Record<string, AppriseFieldValue> = {};
  for (const field of service.fields) {
    const value = values[field.key];
    if (isBlank(value)) continue;
    if (field.type === "bool" && value === (field.default === true)) continue;
    if (field.type === "choice" && value === String(field.default ?? "")) {
      continue;
    }
    payload[field.key] =
      field.type === "int" || field.type === "float" ? Number(value) : value;
  }
  return payload;
}

/** Required lists the form left empty; the combobox has no rules of its own. */
export function missingAppriseLists(
  service: AppriseServiceSchema,
  values: Record<string, AppriseFieldValue>,
): string[] {
  return service.fields
    .filter((field) => field.type === "list" && field.required)
    .filter((field) => isBlank(values[field.key]))
    .map((field) => field.key);
}
