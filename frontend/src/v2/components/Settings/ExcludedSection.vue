<script setup lang="ts">
// ExcludedSection — v2-native rebuild of v1
// `Settings/LibraryManagement/Config/Excluded.vue`. Lets the user view and
// manage scan exclusions (file names, extensions, platforms). Defaults
// from `DEFAULT_EXCLUDED_*` are listed read-only at the bottom.
//
// Visuals follow the mock's settings table pattern (subtle borders,
// uppercase column heads, hairline-divided rows). The "Add" flow opens
// a local RDialog that walks the user through type selection + value
// entry.
import {
  RBtn,
  REmptyState,
  RIcon,
  RTable,
  RTextField,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const snackbar = useSnackbar();

const canEditPlatforms = useCan("platform.edit");

const search = ref("");
const dialogOpen = ref(false);
const newType = ref<string | null>(null);
const newValue = ref("");
const submitting = ref(false);

type SortKey = "value" | "title";
const sortKey = ref<SortKey>("value");
const sortDir = ref<"asc" | "desc">("asc");

type ExclusionDef = {
  key:
    | "EXCLUDED_PLATFORMS"
    | "EXCLUDED_SINGLE_FILES"
    | "EXCLUDED_SINGLE_EXT"
    | "EXCLUDED_MULTI_FILES"
    | "EXCLUDED_MULTI_PARTS_FILES"
    | "EXCLUDED_MULTI_PARTS_EXT";
  title: string;
  description: string;
  icon: string;
};

const exclusionDefs = computed<ExclusionDef[]>(() => [
  {
    key: "EXCLUDED_PLATFORMS",
    title: t("common.platform"),
    description: t("settings.exclusions-platforms-desc"),
    icon: "mdi-gamepad-variant-outline",
  },
  {
    key: "EXCLUDED_SINGLE_FILES",
    title: t("settings.excluded-single-rom-files"),
    description: t("settings.exclusions-single-files-desc"),
    icon: "mdi-file-remove-outline",
  },
  {
    key: "EXCLUDED_SINGLE_EXT",
    title: t("settings.excluded-single-rom-extensions"),
    description: t("settings.exclusions-single-ext-desc"),
    icon: "mdi-file-code-outline",
  },
  {
    key: "EXCLUDED_MULTI_FILES",
    title: t("settings.excluded-multi-rom-files"),
    description: t("settings.exclusions-multi-files-desc"),
    icon: "mdi-file-multiple-outline",
  },
  {
    key: "EXCLUDED_MULTI_PARTS_FILES",
    title: t("settings.excluded-multi-rom-parts-files"),
    description: t("settings.exclusions-multi-parts-files-desc"),
    icon: "mdi-folder-multiple-outline",
  },
  {
    key: "EXCLUDED_MULTI_PARTS_EXT",
    title: t("settings.excluded-multi-rom-parts-extensions"),
    description: t("settings.exclusions-multi-parts-ext-desc"),
    icon: "mdi-file-cog-outline",
  },
]);

const DEFAULT_LIST_MAP: Record<
  ExclusionDef["key"],
  | "DEFAULT_EXCLUDED_DIRS"
  | "DEFAULT_EXCLUDED_FILES"
  | "DEFAULT_EXCLUDED_EXTENSIONS"
> = {
  EXCLUDED_PLATFORMS: "DEFAULT_EXCLUDED_DIRS",
  EXCLUDED_SINGLE_FILES: "DEFAULT_EXCLUDED_FILES",
  EXCLUDED_SINGLE_EXT: "DEFAULT_EXCLUDED_EXTENSIONS",
  EXCLUDED_MULTI_FILES: "DEFAULT_EXCLUDED_DIRS",
  EXCLUDED_MULTI_PARTS_FILES: "DEFAULT_EXCLUDED_FILES",
  EXCLUDED_MULTI_PARTS_EXT: "DEFAULT_EXCLUDED_EXTENSIONS",
};

function isDefault(key: ExclusionDef["key"], value: string): boolean {
  const defaults = config.value[DEFAULT_LIST_MAP[key]] || [];
  return defaults.includes(value);
}

type Row = {
  type: ExclusionDef["key"];
  title: string;
  icon: string;
  value: string;
};

const exclusions = computed<Row[]>(() => {
  const rows: Row[] = [];
  for (const def of exclusionDefs.value) {
    const set = config.value[def.key] || [];
    for (const v of set) {
      if (!isDefault(def.key, v)) {
        rows.push({
          type: def.key,
          title: def.title,
          icon: def.icon,
          value: v,
        });
      }
    }
  }
  return rows;
});

const sortedExclusions = computed(() => {
  const list = [...exclusions.value];
  const dir = sortDir.value === "asc" ? 1 : -1;
  list.sort((a, b) => {
    if (sortKey.value === "title") {
      return (
        a.title.localeCompare(b.title) * dir || a.value.localeCompare(b.value)
      );
    }
    // value
    return (
      a.value.localeCompare(b.value) * dir || a.title.localeCompare(b.title)
    );
  });
  return list;
});

const filteredExclusions = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return sortedExclusions.value;
  return sortedExclusions.value.filter(
    (r) =>
      r.value.toLowerCase().includes(q) || r.title.toLowerCase().includes(q),
  );
});

const defaultExclusions = computed(() => {
  const seen = new Map<string, Row>();
  for (const def of exclusionDefs.value) {
    const set = config.value[def.key] || [];
    for (const v of set) {
      if (isDefault(def.key, v) && !seen.has(v)) {
        seen.set(v, {
          type: def.key,
          title: def.title,
          icon: def.icon,
          value: v,
        });
      }
    }
  }
  return [...seen.values()].sort((a, b) => a.value.localeCompare(b.value));
});

const canEdit = computed(
  () => canEditPlatforms.value && config.value.CONFIG_FILE_WRITABLE,
);

function openCreate() {
  newType.value = null;
  newValue.value = "";
  dialogOpen.value = true;
}

function closeCreate() {
  dialogOpen.value = false;
  newType.value = null;
  newValue.value = "";
}

const selectedDef = computed(() =>
  exclusionDefs.value.find((d) => d.key === newType.value),
);

async function submitExclusion() {
  if (!newType.value || !newValue.value.trim()) return;
  submitting.value = true;
  try {
    await configApi.addExclusion({
      exclusionValue: newValue.value.trim(),
      exclusionType: newType.value,
    });
    if (configStore.isExclusionType(newType.value)) {
      configStore.addExclusion(newType.value, newValue.value.trim());
    }
    snackbar.success("Exclusion added");
    closeCreate();
  } catch (err) {
    snackbar.error(`Could not add exclusion: ${(err as Error).message}`);
  } finally {
    submitting.value = false;
  }
}

async function removeRow(row: Row) {
  try {
    await configApi.deleteExclusion({
      exclusionValue: row.value,
      exclusionType: row.type,
    });
    if (configStore.isExclusionType(row.type)) {
      configStore.removeExclusion(row.value, row.type);
    }
  } catch (err) {
    snackbar.error(`Could not remove exclusion: ${(err as Error).message}`);
  }
}

const columns = computed<RTableColumn[]>(() => [
  {
    key: "value",
    label: t("common.name"),
    sortable: true,
    width: "minmax(0, 1.6fr)",
    skeletonWidth: 160,
  },
  {
    key: "title",
    label: t("common.type"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 140,
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
  if (key !== "value" && key !== "title") return;
  sortKey.value = key;
  sortDir.value = dir;
}
</script>

<template>
  <div class="r-v2-excluded">
    <!-- Toolbar: search + add -->
    <div class="r-v2-excluded__toolbar">
      <RTextField
        v-model="search"
        prefix-label
        hide-details
        aria-label="Search exclusions"
        class="r-v2-excluded__search"
      >
        <template #prefix-label>
          <RIcon icon="mdi-magnify" size="14" />
          {{ t("common.search") }}
        </template>
      </RTextField>
    </div>

    <!-- Active exclusions table or empty state -->
    <div v-if="exclusions.length === 0" class="r-v2-excluded__empty">
      <REmptyState
        icon="mdi-format-list-bulleted"
        :message="t('settings.exclusions-none')"
      />
    </div>
    <RTable
      v-else
      :columns="columns"
      :items="filteredExclusions"
      :item-key="(r) => `${(r as Row).type}:${(r as Row).value}`"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      empty-icon="mdi-folder-search-outline"
      :empty-message="t('common.no-results')"
      row-height="44px"
      @update:sort="onSort"
    >
      <template #cell.value="{ row }">
        <span class="r-v2-excluded__value">{{ (row as Row).value }}</span>
      </template>
      <template #cell.title="{ row }">
        <span class="r-v2-excluded__type">
          <RIcon :icon="(row as Row).icon" size="14" />
          {{ (row as Row).title }}
        </span>
      </template>
      <template #cell.actions="{ row }">
        <RBtn
          v-if="canEdit"
          variant="text"
          size="small"
          icon="mdi-trash-can-outline"
          :aria-label="t('common.delete')"
          :title="t('common.delete')"
          class="r-v2-excluded__delete-btn"
          @click="removeRow(row as Row)"
        />
      </template>
    </RTable>
    <div>
      <RBtn
        v-if="canEdit"
        variant="flat"
        :block="false"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openCreate"
      >
        {{ t("common.add") }}
      </RBtn>
    </div>

    <!-- Defaults (read-only) -->
    <div v-if="defaultExclusions.length > 0" class="r-v2-excluded__defaults">
      <div class="r-v2-excluded__defaults-label">
        {{ t("settings.exclusions-defaults") }}
      </div>
      <ul class="r-v2-excluded__defaults-list">
        <li
          v-for="d in defaultExclusions"
          :key="d.value"
          class="r-v2-excluded__defaults-item"
        >
          <RIcon :icon="d.icon" size="14" />
          <span class="r-v2-excluded__defaults-value">{{ d.value }}</span>
          <span class="r-v2-excluded__defaults-type">{{ d.title }}</span>
        </li>
      </ul>
    </div>

    <!-- Add exclusion dialog -->
    <RDialog
      v-model="dialogOpen"
      icon="mdi-cancel"
      :width="540"
      @close="closeCreate"
    >
      <template #header>
        <span class="r-v2-excluded__dialog-title">
          {{ t("common.add") }}
        </span>
      </template>
      <template #content>
        <div class="r-v2-excluded__dialog-body">
          <p class="r-v2-excluded__dialog-help">
            {{ t("settings.select-exclusion-type") }}
          </p>
          <div class="r-v2-excluded__type-grid">
            <button
              v-for="def in exclusionDefs"
              :key="def.key"
              type="button"
              class="r-v2-excluded__type-card"
              :class="{
                'r-v2-excluded__type-card--active': newType === def.key,
              }"
              :aria-pressed="newType === def.key"
              @click="newType = def.key"
            >
              <RIcon :icon="def.icon" size="22" />
              <span class="r-v2-excluded__type-card-title">{{
                def.title
              }}</span>
              <span class="r-v2-excluded__type-card-desc">
                {{ def.description }}
              </span>
            </button>
          </div>
          <RTextField
            v-model="newValue"
            prefix-label
            :disabled="!newType"
            hide-details
            @keyup.enter="submitExclusion"
          >
            <template #prefix-label>
              <RIcon
                v-if="selectedDef?.icon"
                :icon="selectedDef.icon"
                size="14"
              />
              {{ t("settings.exclusion-value") }}
            </template>
          </RTextField>
        </div>
      </template>
      <template #footer>
        <div class="r-v2-excluded__dialog-actions">
          <RBtn variant="text" @click="closeCreate">
            {{ t("common.cancel") }}
          </RBtn>
          <RBtn
            variant="flat"
            color="primary"
            :loading="submitting"
            :disabled="!newType || !newValue.trim()"
            @click="submitExclusion"
          >
            {{ t("common.confirm") }}
          </RBtn>
        </div>
      </template>
    </RDialog>
  </div>
</template>

<style scoped>
.r-v2-excluded {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-excluded__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-excluded__search {
  flex: 1;
}

.r-v2-excluded__value {
  font-weight: var(--r-font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-excluded__type {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--r-color-fg-muted);
}

.r-v2-excluded__delete-btn {
  color: color-mix(in srgb, var(--r-color-danger) 70%, transparent) !important;
}
.r-v2-excluded__delete-btn:hover {
  color: var(--r-color-danger) !important;
  background: color-mix(
    in srgb,
    var(--r-color-danger) 12%,
    transparent
  ) !important;
}

/* Empty state with CTA below. */
.r-v2-excluded__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 24px 16px 32px;
}

/* Defaults list (read-only). */
.r-v2-excluded__defaults {
  border-top: 1px solid var(--r-color-border);
  padding-top: 16px;
}
.r-v2-excluded__defaults-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
  margin-bottom: 10px;
}
.r-v2-excluded__defaults-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}
.r-v2-excluded__defaults-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  color: var(--r-color-fg-secondary);
  font-size: 12px;
}
.r-v2-excluded__defaults-value {
  font-weight: var(--r-font-weight-medium);
}
.r-v2-excluded__defaults-type {
  margin-left: auto;
  color: var(--r-color-fg-faint);
  font-size: 11px;
}

/* Add-exclusion dialog. */
.r-v2-excluded__dialog-title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-excluded__dialog-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.r-v2-excluded__dialog-help {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: var(--r-color-fg-muted);
}
.r-v2-excluded__type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}
.r-v2-excluded__type-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 14px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  text-align: left;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-excluded__type-card:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
  color: var(--r-color-fg);
}
.r-v2-excluded__type-card--active,
.r-v2-excluded__type-card--active:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 50%,
    transparent
  );
  color: var(--r-color-brand-primary);
}
.r-v2-excluded__type-card-title {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-excluded__type-card-desc {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}
.r-v2-excluded__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--r-color-border);
}
</style>
