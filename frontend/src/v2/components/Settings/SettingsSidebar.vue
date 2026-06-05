<script setup lang="ts">
// SettingsSidebar — vertical grouped nav rendered alongside every Settings
// view via <SettingsShell>. Replaces the previous horizontal pill nav.
//
// Groups mirror the v2 user-menu IA so the dropdown and the in-page
// navigator share the same mental model:
//   • Account  — profile + UI prefs
//   • Library  — folder mappings, providers, paired devices
//   • System   — admin + server stats
//   • Tools    — controller debug (developer-leaning, kept here so it
//                inherits the same chrome as everything else)
//
// Each entry is a <router-link>; the active state is driven by Vue
// Router's `router-link-active` (we add `--active` via active-class). Items
// that the user can't reach (insufficient scopes/role) are filtered out.
//
// Responsive: at <1024px the sidebar collapses to a horizontal scrollable
// strip. Group labels are hidden in that mode — items still appear in
// group order so sequence is preserved.
import { RChip, RIcon } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import storeAuth from "@/stores/auth";
import { useCan } from "@/v2/composables/useCan";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const auth = storeAuth();
const { user, scopes } = storeToRefs(auth);
const isAdmin = useCan("app.admin");

interface Entry {
  icon: string;
  label: string;
  to: { name: string; params?: Record<string, string | number> };
  visible: boolean;
  /** Optional trailing badge text (e.g. "Beta") shown after the label. */
  badge?: string;
}

interface Group {
  key: "account" | "library" | "system" | "tools";
  label: string;
  entries: Entry[];
}

const groups = computed<Group[]>(() => {
  const all: Group[] = [
    {
      key: "account",
      label: t("settings.group-account"),
      entries: [
        {
          icon: "mdi-account-circle",
          label: t("common.profile"),
          to: {
            name: ROUTES.USER_PROFILE,
            params: { user: user.value?.id ?? "" },
          },
          visible: scopes.value.includes("me.write"),
        },
        {
          icon: "mdi-palette",
          label: t("common.user-interface"),
          to: { name: ROUTES.USER_INTERFACE },
          visible: true,
        },
      ],
    },
    {
      key: "library",
      label: t("settings.group-library"),
      entries: [
        {
          icon: "mdi-folder-cog",
          label: t("common.library-management"),
          to: { name: ROUTES.LIBRARY_MANAGEMENT },
          visible: scopes.value.includes("platforms.write"),
        },
        {
          icon: "mdi-database-search",
          label: t("scan.metadata-sources"),
          to: { name: ROUTES.METADATA_SOURCES },
          visible: scopes.value.includes("me.write"),
        },
        {
          icon: "mdi-key-variant",
          label: t("settings.client-api-tokens"),
          to: { name: ROUTES.CLIENT_API_TOKENS },
          visible: scopes.value.includes("me.write"),
        },
      ],
    },
    {
      key: "system",
      label: t("settings.group-system"),
      entries: [
        {
          icon: "mdi-security",
          label: t("common.administration"),
          to: { name: ROUTES.ADMINISTRATION },
          visible: scopes.value.includes("users.write"),
        },
        {
          icon: "mdi-chart-bar",
          label: t("common.server-stats"),
          to: { name: ROUTES.SERVER_STATS },
          visible: isAdmin.value,
        },
      ],
    },
    {
      key: "tools",
      label: t("settings.group-tools"),
      entries: [
        {
          icon: "mdi-controller",
          label: t("settings.controller-debug"),
          to: { name: ROUTES.CONTROLLER_DEBUG },
          visible: true,
          badge: t("common.beta"),
        },
      ],
    },
  ];

  return all
    .map((g) => ({ ...g, entries: g.entries.filter((e) => e.visible) }))
    .filter((g) => g.entries.length > 0);
});
</script>

<template>
  <nav
    class="r-v2-settings-sidebar"
    :aria-label="t('settings.settings-sections')"
  >
    <div
      v-for="group in groups"
      :key="group.key"
      class="r-v2-settings-sidebar__group"
    >
      <div class="r-v2-settings-sidebar__group-label">
        {{ group.label }}
      </div>
      <ul class="r-v2-settings-sidebar__list">
        <li v-for="entry in group.entries" :key="entry.to.name">
          <router-link
            :to="entry.to"
            class="r-v2-settings-sidebar__item"
            active-class="r-v2-settings-sidebar__item--active"
          >
            <RIcon
              :icon="entry.icon"
              size="16"
              class="r-v2-settings-sidebar__icon"
            />
            <span class="r-v2-settings-sidebar__label">{{ entry.label }}</span>
            <RChip
              v-if="entry.badge"
              size="x-small"
              color="primary"
              class="r-v2-settings-sidebar__badge"
            >
              {{ entry.badge }}
            </RChip>
          </router-link>
        </li>
      </ul>
    </div>
  </nav>
</template>

<style scoped>
/* Mock-faithful: flush column with a hairline right border, NO card
   chrome. Items run edge-to-edge so the bg-tint reads as "row selected"
   rather than "pill selected". Group labels are inline at the top of
   each group, small uppercase, very muted. */
/* Sticky column with a hairline right border. The sidebar is glued to
   the top of the viewport (under the navbar) and always fills the full
   visible height so the divider reaches the bottom of the screen. The
   document is the only scrolling container — only the content column
   moves when the user scrolls. */
.r-v2-settings-sidebar {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 24px 0;
  border-right: 1px solid var(--r-color-border);
  position: sticky;
  top: var(--r-nav-h);
  height: calc(100vh - var(--r-nav-h));
  overflow-y: auto;
  scrollbar-width: thin;
}

.r-v2-settings-sidebar__group {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.r-v2-settings-sidebar__group + .r-v2-settings-sidebar__group {
  margin-top: 8px;
}

.r-v2-settings-sidebar__group-label {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-faint);
  padding: 10px 20px 6px;
}

.r-v2-settings-sidebar__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.r-v2-settings-sidebar__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 20px;
  text-decoration: none;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
  white-space: nowrap;
}

.r-v2-settings-sidebar__icon {
  flex-shrink: 0;
}

.r-v2-settings-sidebar__item:hover {
  color: var(--r-color-fg);
  background: var(--r-color-surface);
}

.r-v2-settings-sidebar__item--active,
.r-v2-settings-sidebar__item--active:hover {
  color: var(--r-color-fg);
  background: var(--r-color-surface-hover);
}

/* Below md (< 960): horizontal scrollable strip — items keep their
   group order; group labels disappear so the strip reads as a single
   tab row. Tracks the same flush feel: no card border, just a bottom
   hairline. */
html[data-bp~="sm-and-down"] .r-v2-settings-sidebar {
  flex-direction: row;
  align-items: center;
  gap: 0;
  padding: 6px var(--r-row-pad);
  border-right: none;
  border-bottom: 1px solid var(--r-color-border);
  overflow-x: auto;
  overflow-y: hidden;
  position: static;
  top: auto;
  height: auto;
}
html[data-bp~="sm-and-down"] .r-v2-settings-sidebar__group {
  flex-direction: row;
  flex-shrink: 0;
  align-items: center;
  gap: 0;
}
html[data-bp~="sm-and-down"]
  .r-v2-settings-sidebar__group
  + .r-v2-settings-sidebar__group {
  margin-top: 0;
}
html[data-bp~="sm-and-down"]
  .r-v2-settings-sidebar__group
  + .r-v2-settings-sidebar__group::before {
  content: "";
  width: 1px;
  height: 18px;
  background: var(--r-color-border);
  margin: 0 6px;
  flex-shrink: 0;
}
html[data-bp~="sm-and-down"] .r-v2-settings-sidebar__group-label {
  display: none;
}
html[data-bp~="sm-and-down"] .r-v2-settings-sidebar__list {
  flex-direction: row;
}
html[data-bp~="sm-and-down"] .r-v2-settings-sidebar__item {
  padding: 7px 14px;
  border-radius: var(--r-radius-pill);
}
</style>
