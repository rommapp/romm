<script setup lang="ts">
// FolderMappingsSection — v2-native rebuild of v1
// `Settings/LibraryManagement/Config/FolderMappings.vue`. Lists every
// filesystem folder the scanner sees and lets admins map each one to a
// RomM platform (alias) or to a parent platform's metadata (variant).
// Auto-detected mappings are read-only.
//
// Renders through the shared `RTable` primitive — sortable headers,
// hairline rows, hover tint, skeleton loading state — same chrome as
// every other table surface in the app (gallery list, missing games,
// excluded). Editable Platform / Type cells open `RMenu` pickers via
// `RBtn` activators.
import {
  RBtn,
  RDialog,
  RIcon,
  RTable,
  RTextField,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import configApi from "@/services/api/config";
import platformApi from "@/services/api/platform";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import type { Platform } from "@/stores/platforms";
import FolderMappingPlatformCell from "@/v2/components/Settings/FolderMappingPlatformCell.vue";
import FolderMappingTypeCell from "@/v2/components/Settings/FolderMappingTypeCell.vue";
import { prefetchPlatformIcons } from "@/v2/composables/usePlatformIconCache";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const heartbeat = storeHeartbeat();
const snackbar = useSnackbar();

const supportedPlatforms = ref<Platform[]>([]);
const search = ref("");
const loading = ref(false);
const helpOpen = ref(false);

type RowType = "alias" | "variant" | "auto" | null;
type SortKey = "fsSlug" | "displayName" | "type";

const sortKey = ref<SortKey>("fsSlug");
const sortDir = ref<"asc" | "desc">("asc");

interface Row {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: RowType;
}

const TYPE_ORDER: Record<NonNullable<RowType> | "none", number> = {
  alias: 0,
  variant: 1,
  auto: 2,
  none: 3,
};

const mappings = computed<Row[]>(() => {
  const rows: Row[] = [];
  const folders = heartbeat.value?.FILESYSTEM?.FS_PLATFORMS || [];
  const bindings = config.value.PLATFORMS_BINDING || {};
  const versions = config.value.PLATFORMS_VERSIONS || {};
  const autoSlug: Record<string, string | undefined> = {};

  for (const p of supportedPlatforms.value) autoSlug[p.slug] = p.slug;

  for (const folder of folders) {
    if (bindings[folder]) {
      const slug = bindings[folder];
      const platform = supportedPlatforms.value.find((p) => p.slug === slug);
      rows.push({
        fsSlug: folder,
        slug,
        displayName: platform?.display_name || platform?.name || slug,
        type: "alias",
      });
      continue;
    }
    if (versions[folder]) {
      const slug = versions[folder];
      const platform = supportedPlatforms.value.find((p) => p.slug === slug);
      rows.push({
        fsSlug: folder,
        slug,
        displayName: platform?.display_name || platform?.name || slug,
        type: "variant",
      });
      continue;
    }
    const auto = autoSlug[folder];
    if (auto) {
      const platform = supportedPlatforms.value.find((p) => p.slug === auto);
      rows.push({
        fsSlug: folder,
        slug: auto,
        displayName: platform?.display_name || platform?.name || auto,
        type: "auto",
      });
    } else {
      rows.push({
        fsSlug: folder,
        slug: undefined,
        displayName: undefined,
        type: null,
      });
    }
  }

  return rows;
});

const sortedMappings = computed(() => {
  const list = [...mappings.value];
  const dir = sortDir.value === "asc" ? 1 : -1;
  list.sort((a, b) => {
    if (sortKey.value === "fsSlug") {
      return a.fsSlug.localeCompare(b.fsSlug) * dir;
    }
    if (sortKey.value === "displayName") {
      // Unmapped rows (no displayName) are pushed to the bottom regardless
      // of direction so the visible content stays predictable.
      const aHas = !!a.displayName;
      const bHas = !!b.displayName;
      if (aHas !== bHas) return aHas ? -1 : 1;
      return (a.displayName ?? "").localeCompare(b.displayName ?? "") * dir;
    }
    // type
    const aOrder = TYPE_ORDER[a.type ?? "none"];
    const bOrder = TYPE_ORDER[b.type ?? "none"];
    if (aOrder === bOrder) return a.fsSlug.localeCompare(b.fsSlug);
    return (aOrder - bOrder) * dir;
  });
  return list;
});

const filteredMappings = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return sortedMappings.value;
  return sortedMappings.value.filter(
    (r) =>
      r.fsSlug.toLowerCase().includes(q) ||
      (r.displayName ?? "").toLowerCase().includes(q),
  );
});

// Same check as v1 (OAuth scope) — admin/editor get `platforms.write`
// via FULL_SCOPES / EDIT_SCOPES on the backend. Matches the working
// permission gate exactly, avoiding the v2 useCan-store hydration race
// that was leaving cells unclickable on Settings load.
const canEdit = computed(
  () =>
    authStore.scopes.includes("platforms.write") &&
    config.value.CONFIG_FILE_WRITABLE,
);

const columns = computed<RTableColumn[]>(() => [
  {
    key: "fsSlug",
    label: t("settings.folder-name-header"),
    sortable: true,
    width: "minmax(0, 1.4fr)",
    skeletonWidth: 140,
  },
  {
    key: "platform",
    label: t("settings.romm-platform-header"),
    sortable: true,
    width: "minmax(0, 1.6fr)",
    skeletonWidth: 160,
  },
  {
    key: "type",
    label: t("settings.type-header"),
    sortable: true,
    width: "160px",
    skeletonWidth: 70,
  },
  {
    key: "actions",
    label: "",
    width: "56px",
    align: "end",
    skeletonWidth: 0,
  },
]);

function onSort({ key, dir }: RTableSortPayload) {
  // The "platform" column header drives sorting on `displayName`.
  if (key === "platform") {
    sortKey.value = "displayName";
  } else if (key === "fsSlug" || key === "type") {
    sortKey.value = key;
  } else {
    return;
  }
  sortDir.value = dir;
}

// RTable expects a single string sortKey — translate our internal
// `displayName` back to the column key it shows the chevron next to.
const tableSortKey = computed(() =>
  sortKey.value === "displayName" ? "platform" : sortKey.value,
);

async function setPlatform(row: Row, slug: string | undefined) {
  loading.value = true;
  try {
    if (!slug) {
      // Delete the mapping.
      if (row.type === "alias") {
        await configApi.deletePlatformBindConfig({ fsSlug: row.fsSlug });
      } else if (row.type === "variant") {
        await configApi.deletePlatformVersionConfig({ fsSlug: row.fsSlug });
      }
      await configStore.fetchConfig();
      snackbar.success(t("settings.platform-mapping-deleted"));
      return;
    }
    if (row.type === null) {
      await configApi.addPlatformBindConfig({ fsSlug: row.fsSlug, slug });
      await configStore.fetchConfig();
      snackbar.success(t("settings.platform-mapping-created"));
      return;
    }
    if (row.type === "auto") {
      await configApi.addPlatformBindConfig({ fsSlug: row.fsSlug, slug });
      await configStore.fetchConfig();
      snackbar.success(t("settings.platform-mapping-updated"));
      return;
    }
    if (row.type === "alias") {
      await configApi.deletePlatformBindConfig({ fsSlug: row.fsSlug });
      await configApi.addPlatformBindConfig({ fsSlug: row.fsSlug, slug });
      await configStore.fetchConfig();
      snackbar.success(t("settings.platform-mapping-updated"));
      return;
    }
    if (row.type === "variant") {
      await configApi.deletePlatformVersionConfig({ fsSlug: row.fsSlug });
      await configApi.addPlatformVersionConfig({ fsSlug: row.fsSlug, slug });
      await configStore.fetchConfig();
      snackbar.success(t("settings.platform-mapping-updated"));
    }
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(t("settings.unable-to-update-platform-mapping", { detail }));
  } finally {
    loading.value = false;
  }
}

async function setType(row: Row, newType: "alias" | "variant") {
  if (!row.slug || row.type === newType) return;
  loading.value = true;
  try {
    if (row.type === "alias") {
      await configApi.deletePlatformBindConfig({ fsSlug: row.fsSlug });
    } else if (row.type === "variant") {
      await configApi.deletePlatformVersionConfig({ fsSlug: row.fsSlug });
    }
    if (newType === "alias") {
      await configApi.addPlatformBindConfig({
        fsSlug: row.fsSlug,
        slug: row.slug,
      });
    } else {
      await configApi.addPlatformVersionConfig({
        fsSlug: row.fsSlug,
        slug: row.slug,
      });
    }
    await configStore.fetchConfig();
    snackbar.success(t("settings.platform-mapping-updated"));
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(t("settings.unable-to-update-platform-mapping", { detail }));
  } finally {
    loading.value = false;
  }
}

const initialLoading = ref(false);

onMounted(async () => {
  initialLoading.value = true;
  loading.value = true;
  try {
    const { data } = await platformApi.getSupportedPlatforms();
    supportedPlatforms.value = data || [];
    // Populate the in-memory icon cache so every PlatformIcon
    // rendered by the table rows + Platform picker reads blob URLs
    // instead of refetching. Fires in idle time, non-blocking.
    prefetchPlatformIcons(supportedPlatforms.value.map((p) => p.slug));
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(t("settings.unable-to-get-supported-platforms", { detail }));
  } finally {
    loading.value = false;
    initialLoading.value = false;
  }
});
</script>

<template>
  <div class="r-v2-mappings">
    <div class="r-v2-mappings__toolbar">
      <RTextField
        v-model="search"
        prefix-label="inline"
        :placeholder="t('common.search')"
        hide-details
        aria-label="Search folder mappings"
        class="r-v2-mappings__search"
      >
        <template #prefix-label>
          <RIcon icon="mdi-magnify" size="14" />
        </template>
      </RTextField>
    </div>

    <RTable
      :columns="columns"
      :items="filteredMappings"
      item-key="fsSlug"
      :loading="initialLoading"
      :sort-key="tableSortKey"
      :sort-dir="sortDir"
      empty-icon="mdi-folder-search-outline"
      :empty-message="t('common.no-results')"
      row-height="44px"
      @update:sort="onSort"
    >
      <!-- Help affordance lives next to the "Type" header label — a
           small `?` icon that opens the mapping-types dialog. Sits
           where the user is most likely to wonder what alias / variant
           mean (instead of competing with the search in the toolbar). -->
      <template #header.type>
        <RBtn
          variant="text"
          size="x-small"
          icon="mdi-help-circle-outline"
          class="r-v2-mappings__help-icon"
          :aria-label="t('settings.mapping-types')"
          :title="t('settings.mapping-types')"
          @click="helpOpen = true"
        />
      </template>

      <template #cell.fsSlug="{ row }">
        <span class="r-v2-mappings__folder">{{ (row as Row).fsSlug }}</span>
      </template>

      <template #cell.platform="{ row }">
        <FolderMappingPlatformCell
          :row="row as Row"
          :supported-platforms="supportedPlatforms"
          :can-edit="canEdit"
          @select="(slug) => setPlatform(row as Row, slug)"
        />
      </template>

      <template #cell.type="{ row }">
        <FolderMappingTypeCell
          :row="row as Row"
          :can-edit="canEdit"
          @select="(t) => setType(row as Row, t)"
        />
      </template>

      <template #cell.actions="{ row }">
        <RBtn
          v-if="canEdit && (row as Row).type !== 'auto' && (row as Row).slug"
          variant="text"
          size="small"
          icon="mdi-trash-can-outline"
          :aria-label="t('common.delete')"
          :title="t('common.delete')"
          class="r-v2-mappings__delete-btn"
          @click="setPlatform(row as Row, undefined)"
        />
      </template>
    </RTable>

    <!-- Help dialog — replaces the previous toolbar tooltip. Same
         alias/variant copy, plus a footer note about mutual exclusion.
         Auto isn't covered here on purpose: it's system-detected and
         users can't pick it manually. -->
    <RDialog
      v-model="helpOpen"
      icon="mdi-folder-multiple-outline"
      :width="520"
      @close="helpOpen = false"
    >
      <template #header>
        <span class="r-v2-mappings__help-title">
          {{ t("settings.mapping-types") }}
        </span>
      </template>
      <template #content>
        <div class="r-v2-mappings__help-body">
          <section class="r-v2-mappings__help-row">
            <h3 class="r-v2-mappings__help-row-title">
              {{ t("settings.folder-alias") }}
            </h3>
            <p>{{ t("settings.folder-mappings-tooltip-aliases") }}</p>
          </section>
          <section class="r-v2-mappings__help-row">
            <h3 class="r-v2-mappings__help-row-title">
              {{ t("settings.platform-variant") }}
            </h3>
            <p>{{ t("settings.folder-mappings-tooltip-variants") }}</p>
          </section>
          <p class="r-v2-mappings__help-foot">
            <RIcon icon="mdi-information-outline" size="14" color="primary" />
            <span>{{ t("settings.folder-mappings-mutually-exclusive") }}</span>
          </p>
        </div>
      </template>
      <template #footer>
        <div class="r-v2-mappings__help-footer">
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-check"
            @click="helpOpen = false"
          >
            {{ t("common.got-it") }}
          </RBtn>
        </div>
      </template>
    </RDialog>
  </div>
</template>

<style scoped>
.r-v2-mappings {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-mappings__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-mappings__search {
  flex: 1;
}

/* Help affordance inside the "Type" column header — a small, muted
   icon that tints to fg on hover. Negative inline-end margin keeps it
   visually attached to the label without enlarging the header gap. */
.r-v2-mappings__help-icon {
  color: var(--r-color-fg-faint) !important;
  width: 22px !important;
  height: 22px !important;
  min-width: 0 !important;
  margin-left: 2px !important;
}
.r-v2-mappings__help-icon:hover {
  color: var(--r-color-fg) !important;
  background: var(--r-color-surface-hover) !important;
}

.r-v2-mappings__folder {
  font-weight: var(--r-font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Delete row action — danger-tinted icon RBtn. */
.r-v2-mappings__delete-btn {
  color: color-mix(in srgb, var(--r-color-danger) 70%, transparent) !important;
}
.r-v2-mappings__delete-btn:hover {
  color: var(--r-color-danger) !important;
  background: color-mix(
    in srgb,
    var(--r-color-danger) 12%,
    transparent
  ) !important;
}

/* Help dialog — alias / variant explanation. Two stacked sections
   with a footer note about mutual exclusion. */
.r-v2-mappings__help-title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-mappings__help-body {
  padding: 18px 24px 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.r-v2-mappings__help-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-mappings__help-row-title {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-brand-primary);
}
.r-v2-mappings__help-row p {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--r-color-fg-secondary);
}
.r-v2-mappings__help-foot {
  margin: 4px 0 0;
  padding: 10px 12px;
  display: inline-flex;
  align-items: flex-start;
  gap: 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
  color: var(--r-color-fg-secondary);
  font-size: 12.5px;
  line-height: 1.5;
}
.r-v2-mappings__help-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
}
</style>
