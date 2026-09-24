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
import { count, list, text } from "@/v2/utils/eventData";
import { joinNames } from "@/v2/utils/lists";
import { METADATA_PROVIDERS } from "@/v2/utils/metadataProviders";
import { formatPlaytime } from "@/v2/utils/time";

export interface AuditEventView {
  icon: string;
  /** A color token: the category's, or danger for something that failed. */
  tone: string;
  title: string;
  detail: string | null;
  /** Where the target lives, or null once it's gone. */
  to: RouteLocationRaw | null;
}

type AuditData = AuditEventSchema["data"];
type Describer = (
  event: AuditEventSchema,
  target: string,
) => Omit<AuditEventView, "to" | "tone">;

const t = i18n.global.t;

export const AUDIT_CATEGORIES: readonly AuditCategory[] = [
  "consumption",
  "library",
  "collections",
  "operations",
  "security",
];

function kebab(value: string): string {
  return value.replaceAll("_", "-");
}

function names(values: string[]): string | null {
  return values.length ? joinNames(values, i18n.global.locale.value) : null;
}

function fields(value: unknown): string | null {
  const labels = names(list(value).map((f) => t(`audit.field-${kebab(f)}`)));
  return labels ? t("audit.detail-changed", { fields: labels }) : null;
}

function change(value: unknown): { from: string; to: string } | null {
  if (!value || typeof value !== "object") return null;
  const { from, to } = value as Record<string, unknown>;
  return { from: String(from ?? ""), to: String(to ?? "") };
}

function providers(data: AuditData): string | null {
  const ids = data.providers;
  if (!ids || typeof ids !== "object") return null;
  return names(
    Object.keys(ids).map(
      (key) =>
        METADATA_PROVIDERS.find((p) => p.key === key)?.name ??
        key.replace(/_id$/, "").toUpperCase(),
    ),
  );
}

function size(data: AuditData): string | null {
  const bytes = count(data.size_bytes);
  return bytes ? formatBytes(bytes) : null;
}

function joinDetails(...parts: (string | null)[]): string | null {
  const present = parts.filter((p): p is string => !!p);
  return present.length ? present.join(" · ") : null;
}

function principal(data: AuditData): string {
  const from = data.from;
  if (!from || typeof from !== "object") return "";
  const { name, id } = from as Record<string, unknown>;
  return text(name) ?? `#${String(id ?? "")}`;
}

// The sentence names the target; `detail` adds a muted second line.
function simple(
  icon: string,
  key: string,
  detail: (event: AuditEventSchema) => string | null = () => null,
): Describer {
  return (event, target) => ({
    icon,
    title: t(key, { target }),
    detail: detail(event),
  });
}

// A sentence about a number of games, such as roms added to a collection.
function counted(icon: string, key: string): Describer {
  return (event, target) => {
    const n = count(event.data.count);
    return { icon, title: t(key, n, { named: { n, target } }), detail: null };
  };
}

function visibility(icon: string, key: string): Describer {
  return (event, target) => ({
    icon,
    title: t(key, { target, principal: principal(event.data) }),
    detail: null,
  });
}

function edited(icon: string, key: string): Describer {
  return simple(icon, key, (event) => {
    const renamed = change(event.data.name);
    return joinDetails(
      fields(event.data.changed),
      renamed ? t("audit.detail-renamed", renamed) : null,
    );
  });
}

const deletedFromDisk = (event: AuditEventSchema) =>
  event.data.deleted_from_fs ? t("audit.detail-deleted-from-disk") : null;

const fileAndSize = (event: AuditEventSchema) =>
  joinDetails(text(event.data.file_name), size(event.data));

const DESCRIBERS: Record<AuditAction, Describer> = {
  "rom.download": simple(
    "mdi-download",
    "audit.action-rom-download",
    fileAndSize,
  ),
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
  "rom.player_load": simple(
    "mdi-controller",
    "audit.action-rom-player-load",
    fileAndSize,
  ),
  "rom.play": simple("mdi-play-circle-outline", "audit.action-rom-play", (e) =>
    formatPlaytime(
      count(e.data.duration_ms) / 1000,
      toBrowserLocale(i18n.global.locale.value),
    ),
  ),

  "rom.upload": (event, target) => ({
    icon: "mdi-cloud-upload-outline",
    title: t("audit.action-rom-upload", {
      target,
      file: text(event.data.file_name) ?? "",
    }),
    detail: size(event.data),
  }),
  "rom.create": simple("mdi-plus-box-outline", "audit.action-rom-create"),
  "rom.edit": edited("mdi-pencil-outline", "audit.action-rom-edit"),
  "rom.match": simple("mdi-link-variant", "audit.action-rom-match", (e) =>
    providers(e.data),
  ),
  "rom.unmatch": simple(
    "mdi-link-variant-off",
    "audit.action-rom-unmatch",
    (e) => providers(e.data),
  ),
  "rom.delete": simple(
    "mdi-trash-can-outline",
    "audit.action-rom-delete",
    (e) => joinDetails(text(e.data.platform), deletedFromDisk(e)),
  ),
  "rom.file_delete": simple(
    "mdi-file-remove-outline",
    "audit.action-rom-file-delete",
    (e) => text(e.data.file_name),
  ),
  "platform.create": simple(
    "mdi-gamepad-variant-outline",
    "audit.action-platform-create",
  ),
  "platform.edit": edited("mdi-pencil-outline", "audit.action-platform-edit"),
  "platform.delete": simple(
    "mdi-trash-can-outline",
    "audit.action-platform-delete",
  ),
  "firmware.upload": simple("mdi-chip", "audit.action-firmware-upload", (e) =>
    names(list(e.data.file_names)),
  ),
  "firmware.delete": simple(
    "mdi-trash-can-outline",
    "audit.action-firmware-delete",
    deletedFromDisk,
  ),
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
  "collection.edit": simple(
    "mdi-bookmark-outline",
    "audit.action-collection-edit",
    (e) => {
      const added = count(e.data.added);
      const removed = count(e.data.removed);
      return joinDetails(
        fields(e.data.changed),
        added
          ? t("audit.detail-games-added", added, { named: { n: added } })
          : null,
        removed
          ? t("audit.detail-games-removed", removed, { named: { n: removed } })
          : null,
      );
    },
  ),
  "collection.delete": simple(
    "mdi-bookmark-remove-outline",
    "audit.action-collection-delete",
  ),
  "collection.add_roms": counted(
    "mdi-bookmark-plus-outline",
    "audit.action-collection-add-roms",
  ),
  "collection.remove_roms": counted(
    "mdi-bookmark-minus-outline",
    "audit.action-collection-remove-roms",
  ),
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

  "scan.start": simple("mdi-radar", "audit.action-scan-start"),
  "scan.finish": (event) => {
    const status = text(event.data.status);
    if (status === "failed") {
      return {
        icon: "mdi-radar",
        title: t("audit.action-scan-failed"),
        detail: text(event.data.error),
      };
    }
    const n = count(event.data.new_roms);
    return {
      icon: "mdi-radar",
      title:
        status === "stopped"
          ? t("audit.action-scan-stopped")
          : t("audit.action-scan-finish"),
      detail: t("audit.detail-new-games", n, { named: { n } }),
    };
  },
  "scan.stop": simple("mdi-stop-circle-outline", "audit.action-scan-stop"),
  "task.run": simple("mdi-pulse", "audit.action-task-run"),

  "auth.login": simple("mdi-login", "audit.action-auth-login"),
  "auth.login_failed": (event) => {
    const reason = text(event.data.reason);
    const username = text(event.data.username);
    return {
      icon: "mdi-account-alert-outline",
      title: username
        ? t("audit.action-auth-login-failed", { username })
        : t("audit.action-auth-login-failed-unknown"),
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
  "user.register": simple(
    "mdi-account-plus-outline",
    "audit.action-user-register",
  ),
  "user.edit": simple(
    "mdi-account-edit-outline",
    "audit.action-user-edit",
    (e) => {
      const role = change(e.data.role);
      return joinDetails(
        fields(e.data.changed),
        role
          ? t("audit.detail-role", {
              from: t(`settings.role-${role.from}`),
              to: t(`settings.role-${role.to}`),
            })
          : null,
      );
    },
  ),
  "user.delete": simple(
    "mdi-account-remove-outline",
    "audit.action-user-delete",
  ),
  "user.permissions_edit": simple(
    "mdi-shield-account-outline",
    "audit.action-user-permissions-edit",
    (e) => text(e.data.group),
  ),
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
  "visibility.hide": visibility(
    "mdi-eye-off-outline",
    "audit.action-visibility-hide",
  ),
  "visibility.unhide": visibility(
    "mdi-eye-outline",
    "audit.action-visibility-unhide",
  ),
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
  "device.approve": simple(
    "mdi-cellphone-link",
    "audit.action-device-approve",
    (e) => text(e.data.client),
  ),
};

const CATEGORY_TONES: Record<AuditCategory, string> = {
  consumption: "var(--r-color-brand-primary)",
  library: "var(--r-color-info)",
  collections: "var(--r-color-brand-accent)",
  operations: "var(--r-color-brand-secondary)",
  security: "var(--r-color-warning)",
};

function toneOf(event: AuditEventSchema): string {
  if (event.action === "auth.login_failed" || event.data.status === "failed") {
    return "var(--r-color-danger)";
  }
  return CATEGORY_TONES[event.category ?? "operations"];
}

function targetRoute(event: AuditEventSchema): RouteLocationRaw | null {
  const id = event.target_id;
  // What was deleted has nowhere left to link to.
  if (!id || event.action.endsWith(".delete")) return null;
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
    tone: CATEGORY_TONES.operations,
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
      tone: toneOf(event),
      to: targetRoute(event),
    };
  } catch (error) {
    // `data` is free-form JSON, so one odd row must not blank the whole log.
    console.error(`Could not describe audit event ${event.id}:`, error);
    return fallback(event, target);
  }
}
