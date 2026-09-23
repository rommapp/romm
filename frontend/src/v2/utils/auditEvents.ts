// Each audit event reads as a sentence built from its action and `data`, so it
// is written in the language of whoever opens the log.
import type { RouteLocationRaw } from "vue-router";
import type {
  AuditAction,
  AuditCategory,
  AuditEventSchema,
} from "@/__generated__";
import i18n from "@/locales";
import { ROUTES } from "@/plugins/routeNames";
import { formatBytes, toBrowserLocale } from "@/utils";
import { METADATA_PROVIDERS } from "@/v2/utils/metadataProviders";
import { formatPlaytime } from "@/v2/utils/time";

export interface AuditEventView {
  icon: string;
  title: string;
  detail: string | null;
  /** Where the target lives, or null once it's gone. */
  to: RouteLocationRaw | null;
}

type AuditData = AuditEventSchema["data"];
type Describer = (
  event: AuditEventSchema,
  target: string,
) => Omit<AuditEventView, "to">;

const t = i18n.global.t;

export const AUDIT_CATEGORIES: readonly AuditCategory[] = [
  "consumption",
  "library",
  "collections",
  "operations",
  "security",
];

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v) => typeof v === "string") : [];
}

function kebab(value: string): string {
  return value.replaceAll("_", "-");
}

function fields(value: unknown): string | null {
  const labels = list(value).map((field) => t(`audit.field-${kebab(field)}`));
  return labels.length
    ? t("audit.detail-changed", { fields: labels.join(", ") })
    : null;
}

function change(value: unknown): { from: string; to: string } | null {
  if (!value || typeof value !== "object") return null;
  const { from, to } = value as Record<string, unknown>;
  return { from: String(from ?? "—"), to: String(to ?? "—") };
}

function providers(data: AuditData): string | null {
  const ids = data.providers;
  if (!ids || typeof ids !== "object") return null;
  const names = Object.keys(ids).map(
    (key) =>
      METADATA_PROVIDERS.find((p) => p.key === key)?.name ??
      key.replace(/_id$/, "").toUpperCase(),
  );
  return names.length ? names.join(", ") : null;
}

function joinDetails(...parts: (string | null)[]): string | null {
  const present = parts.filter((p): p is string => !!p);
  return present.length ? present.join(" · ") : null;
}

function simple(icon: string, key: string): Describer {
  return (_event, target) => ({
    icon,
    title: t(key, { target }),
    detail: null,
  });
}

function edited(icon: string, key: string): Describer {
  return (event, target) => {
    const renamed = change(event.data.name);
    return {
      icon,
      title: t(key, { target }),
      detail: joinDetails(
        fields(event.data.changed),
        renamed ? t("audit.detail-renamed", renamed) : null,
      ),
    };
  };
}

function download(event: AuditEventSchema): string | null {
  const size = count(event.data.size_bytes);
  return joinDetails(
    text(event.data.file_name),
    size ? formatBytes(size) : null,
  );
}

const DESCRIBERS: Record<AuditAction, Describer> = {
  "rom.download": (event, target) => ({
    icon: "mdi-download",
    title: t("audit.action-rom-download", { target }),
    detail: download(event),
  }),
  "rom.bulk_download": (event, target) => {
    const n = count(event.data.count);
    return {
      icon: "mdi-download-multiple",
      title: event.target_type
        ? t("audit.action-rom-bulk-download", n, { named: { n, target } })
        : t("audit.action-rom-bulk-download-selection", n, { named: { n } }),
      detail: null,
    };
  },
  "rom.play": (event, target) => ({
    icon: "mdi-play-circle-outline",
    title: t("audit.action-rom-play", { target }),
    detail: formatPlaytime(
      count(event.data.duration_ms) / 1000,
      toBrowserLocale(i18n.global.locale.value),
    ),
  }),

  "rom.upload": (event, target) => ({
    icon: "mdi-cloud-upload-outline",
    title: t("audit.action-rom-upload", {
      target,
      file: text(event.data.file_name) ?? "",
    }),
    detail: count(event.data.size_bytes)
      ? formatBytes(count(event.data.size_bytes))
      : null,
  }),
  "rom.create": simple("mdi-plus-box-outline", "audit.action-rom-create"),
  "rom.edit": edited("mdi-pencil-outline", "audit.action-rom-edit"),
  "rom.match": (event, target) => ({
    icon: "mdi-link-variant",
    title: t("audit.action-rom-match", { target }),
    detail: providers(event.data),
  }),
  "rom.unmatch": (event, target) => ({
    icon: "mdi-link-variant-off",
    title: t("audit.action-rom-unmatch", { target }),
    detail: providers(event.data),
  }),
  "rom.delete": (event, target) => ({
    icon: "mdi-trash-can-outline",
    title: t("audit.action-rom-delete", { target }),
    detail: joinDetails(
      text(event.data.platform),
      event.data.deleted_from_fs ? t("audit.detail-deleted-from-disk") : null,
    ),
  }),
  "rom.file_delete": (event, target) => ({
    icon: "mdi-file-remove-outline",
    title: t("audit.action-rom-file-delete", { target }),
    detail: text(event.data.file_name),
  }),
  "platform.create": simple(
    "mdi-gamepad-variant-outline",
    "audit.action-platform-create",
  ),
  "platform.edit": edited("mdi-pencil-outline", "audit.action-platform-edit"),
  "platform.delete": simple(
    "mdi-trash-can-outline",
    "audit.action-platform-delete",
  ),
  "firmware.upload": (event, target) => ({
    icon: "mdi-chip",
    title: t("audit.action-firmware-upload", { target }),
    detail: list(event.data.file_names).join(", ") || null,
  }),
  "firmware.delete": (event, target) => ({
    icon: "mdi-trash-can-outline",
    title: t("audit.action-firmware-delete", { target }),
    detail: event.data.deleted_from_fs
      ? t("audit.detail-deleted-from-disk")
      : null,
  }),
  "config.update": (event) => {
    const setting = text(event.data.setting);
    const values = [event.data.fs_slug, event.data.slug, event.data.value]
      .map(text)
      .filter((v): v is string => !!v);
    return {
      icon: "mdi-cog-outline",
      title: t("audit.action-config-update", {
        setting: setting ? t(`audit.config-${kebab(setting)}`) : "",
      }),
      detail: values.join(" → ") || null,
    };
  },

  "collection.create": simple(
    "mdi-bookmark-plus-outline",
    "audit.action-collection-create",
  ),
  "collection.edit": (event, target) => {
    const added = count(event.data.added);
    const removed = count(event.data.removed);
    return {
      icon: "mdi-bookmark-outline",
      title: t("audit.action-collection-edit", { target }),
      detail: joinDetails(
        fields(event.data.changed),
        added
          ? t("audit.detail-games-added", added, { named: { n: added } })
          : null,
        removed
          ? t("audit.detail-games-removed", removed, { named: { n: removed } })
          : null,
      ),
    };
  },
  "collection.delete": simple(
    "mdi-bookmark-remove-outline",
    "audit.action-collection-delete",
  ),
  "collection.add_roms": (event, target) => {
    const n = count(event.data.count);
    return {
      icon: "mdi-bookmark-plus-outline",
      title: t("audit.action-collection-add-roms", n, { named: { n, target } }),
      detail: null,
    };
  },
  "collection.remove_roms": (event, target) => {
    const n = count(event.data.count);
    return {
      icon: "mdi-bookmark-minus-outline",
      title: t("audit.action-collection-remove-roms", n, {
        named: { n, target },
      }),
      detail: null,
    };
  },
  "smart_collection.create": simple(
    "mdi-bookmark-plus-outline",
    "audit.action-smart-collection-create",
  ),
  "smart_collection.edit": simple(
    "mdi-bookmark-outline",
    "audit.action-smart-collection-edit",
  ),
  "smart_collection.delete": simple(
    "mdi-bookmark-remove-outline",
    "audit.action-smart-collection-delete",
  ),

  "scan.start": () => ({
    icon: "mdi-radar",
    title: t("audit.action-scan-start"),
    detail: null,
  }),
  "scan.finish": (event) => {
    const status = text(event.data.status);
    const n = count(event.data.new_roms);
    if (status === "failed") {
      return {
        icon: "mdi-radar",
        title: t("audit.action-scan-failed"),
        detail: text(event.data.error),
      };
    }
    return {
      icon: "mdi-radar",
      title:
        status === "stopped"
          ? t("audit.action-scan-stopped")
          : t("audit.action-scan-finish"),
      detail: t("audit.detail-new-games", n, { named: { n } }),
    };
  },
  "scan.stop": () => ({
    icon: "mdi-stop-circle-outline",
    title: t("audit.action-scan-stop"),
    detail: null,
  }),
  "task.run": simple("mdi-pulse", "audit.action-task-run"),

  "auth.login": () => ({
    icon: "mdi-login",
    title: t("audit.action-auth-login"),
    detail: null,
  }),
  "auth.login_failed": (event) => {
    const reason = text(event.data.reason);
    return {
      icon: "mdi-account-alert-outline",
      title: t("audit.action-auth-login-failed", {
        username: text(event.data.username) ?? "",
      }),
      detail: reason ? t(`audit.detail-login-${reason}`) : null,
    };
  },
  "auth.password_reset_request": simple(
    "mdi-lock-question",
    "audit.action-auth-password-reset-request",
  ),
  "auth.password_reset": simple(
    "mdi-lock-reset",
    "audit.action-auth-password-reset",
  ),
  "user.create": simple("mdi-account-plus-outline", "audit.action-user-create"),
  "user.register": () => ({
    icon: "mdi-account-plus-outline",
    title: t("audit.action-user-register"),
    detail: null,
  }),
  "user.edit": (event, target) => {
    const role = change(event.data.role);
    return {
      icon: "mdi-account-edit-outline",
      title: t("audit.action-user-edit", { target }),
      detail: joinDetails(
        fields(event.data.changed),
        role
          ? t("audit.detail-role", {
              from: t(`settings.role-${role.from}`),
              to: t(`settings.role-${role.to}`),
            })
          : null,
      ),
    };
  },
  "user.delete": simple(
    "mdi-account-remove-outline",
    "audit.action-user-delete",
  ),
  "user.permissions_edit": (event, target) => ({
    icon: "mdi-shield-account-outline",
    title: t("audit.action-user-permissions-edit", { target }),
    detail: text(event.data.group),
  }),
  "permission_group.create": simple(
    "mdi-shield-plus-outline",
    "audit.action-permission-group-create",
  ),
  "permission_group.edit": simple(
    "mdi-shield-edit-outline",
    "audit.action-permission-group-edit",
  ),
  "permission_group.delete": simple(
    "mdi-shield-remove-outline",
    "audit.action-permission-group-delete",
  ),
  "visibility.hide": (event, target) => ({
    icon: "mdi-eye-off-outline",
    title: t("audit.action-visibility-hide", {
      target,
      principal: principal(event.data),
    }),
    detail: null,
  }),
  "visibility.unhide": (event, target) => ({
    icon: "mdi-eye-outline",
    title: t("audit.action-visibility-unhide", {
      target,
      principal: principal(event.data),
    }),
    detail: null,
  }),
  "client_token.create": simple(
    "mdi-key-plus",
    "audit.action-client-token-create",
  ),
  "client_token.regenerate": simple(
    "mdi-key-change",
    "audit.action-client-token-regenerate",
  ),
  "client_token.revoke": simple(
    "mdi-key-remove",
    "audit.action-client-token-revoke",
  ),
  "device.approve": (event, target) => ({
    icon: "mdi-cellphone-link",
    title: t("audit.action-device-approve", { target }),
    detail: text(event.data.client),
  }),
};

function principal(data: AuditData): string {
  const from = data.from;
  if (!from || typeof from !== "object") return "";
  const { name, id } = from as Record<string, unknown>;
  return text(name) ?? `#${String(id ?? "")}`;
}

const DELETES = new Set<string>([
  "rom.delete",
  "platform.delete",
  "firmware.delete",
  "collection.delete",
  "smart_collection.delete",
  "user.delete",
  "permission_group.delete",
  "client_token.revoke",
]);

function targetRoute(event: AuditEventSchema): RouteLocationRaw | null {
  const id = event.target_id;
  if (!id || DELETES.has(event.action)) return null;
  switch (event.target_type) {
    case "rom":
      return { name: ROUTES.ROM, params: { rom: id } };
    case "platform":
      return { name: ROUTES.PLATFORM, params: { platform: id } };
    case "collection":
      return { name: ROUTES.COLLECTION, params: { collection: id } };
    case "smart_collection":
      return { name: ROUTES.SMART_COLLECTION, params: { collection: id } };
    case "virtual_collection":
      return { name: ROUTES.VIRTUAL_COLLECTION, params: { collection: id } };
    default:
      return null;
  }
}

function fallback(event: AuditEventSchema, target: string): AuditEventView {
  return {
    icon: "mdi-help-circle-outline",
    title: [event.action, target].filter(Boolean).join(" "),
    detail: null,
    to: null,
  };
}

function isKnownAction(action: string): action is AuditAction {
  return Object.hasOwn(DESCRIBERS, action);
}

export function describeAuditEvent(event: AuditEventSchema): AuditEventView {
  const target =
    event.target_name ?? (event.target_id ? `#${event.target_id}` : "");
  if (!isKnownAction(event.action)) return fallback(event, target);
  try {
    return {
      ...DESCRIBERS[event.action](event, target),
      to: targetRoute(event),
    };
  } catch (error) {
    // `data` is free-form JSON, so one odd row must not blank the whole log.
    console.error(`Could not describe audit event ${event.id}:`, error);
    return fallback(event, target);
  }
}
