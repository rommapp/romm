<script setup lang="ts">
// FolderMappingPlatformCell — editable Platform cell for the folder
// mappings table.
//
// Uses the shared PlatformSelect with `itemKey="slug"` (the table
// works in slug-space, not platform id) and overrides `#selection`
// to read from the row directly — when a row references a slug that
// isn't in `supportedPlatforms` (loading, removed, …), the default
// selection rendering would crash on the destructure. Reading from
// the row keeps the cell coherent in those edge states.
//
// The full supported-platforms list is owned by the parent
// (`PlatformsStatsSection` / `FolderMappingsSection`) — fetch logic
// stays out of this cell.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";

type RowType = "alias" | "variant" | "auto" | null;

interface Row {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: RowType;
}

interface Props {
  row: Row;
  supportedPlatforms: Platform[];
  canEdit: boolean;
}
const props = defineProps<Props>();

const emit = defineEmits<{
  /** New platform slug (or undefined to clear the mapping). */
  (e: "select", slug: string | undefined): void;
}>();

const { t } = useI18n();

const sortedPlatforms = computed(() =>
  [...props.supportedPlatforms].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

const modelSlug = computed({
  get: () => props.row.slug ?? null,
  set: (next: unknown) =>
    emit("select", typeof next === "string" ? next : undefined),
});
</script>

<template>
  <PlatformSelect
    v-if="canEdit"
    v-model="modelSlug"
    :items="sortedPlatforms"
    item-key="slug"
    hide-details
    density="compact"
    variant="plain"
    :placeholder="t('common.select')"
    :search-placeholder="t('common.search')"
    class="r-v2-fmpc"
  >
    <!-- Drive selection rendering from `row` directly — see header
         comment for why item.raw can't be trusted here. -->
    <template #selection>
      <span class="r-v2-fmpc__selection">
        <CachedPlatformIcon
          v-if="row.slug"
          :slug="row.slug"
          :name="row.displayName ?? row.slug"
          :size="20"
        />
        <span class="r-v2-fmpc__name">
          {{ row.displayName ?? row.slug }}
        </span>
      </span>
    </template>
    <!-- Use the cached icon variant in the dropdown rows too — the
         table is the heaviest consumer of platform icons in the app
         (one per row × every folder mapping). Keeps the table and the
         dropdown visually aligned and warm-cache fast. -->
    <template #item="{ props: itemProps, item }">
      <li v-bind="itemProps">
        <CachedPlatformIcon
          :slug="(item.raw as Platform).slug"
          :name="(item.raw as Platform).display_name"
          :size="20"
        />
        <span class="r-select__item-title">{{ item.title }}</span>
      </li>
    </template>
  </PlatformSelect>
  <span v-else class="r-v2-fmpc__readonly">
    <CachedPlatformIcon
      v-if="row.slug"
      :slug="row.slug"
      :name="row.displayName ?? row.slug"
      :size="20"
    />
    <span v-if="row.slug" class="r-v2-fmpc__name">{{ row.displayName }}</span>
    <span v-else class="r-v2-fmpc__placeholder">—</span>
    <RIcon
      v-if="!row.slug"
      icon="mdi-help-circle-outline"
      size="14"
      class="r-v2-fmpc__placeholder"
    />
  </span>
</template>

<style scoped>
/* Lock the field to the column's width — PlatformSelect / RSelect
   size their inner field to content by default, which would make each
   row's cell as wide as its platform name. The visible width then
   shifts as the user scrolls the table (different rows visible,
   different widths). */
.r-v2-fmpc {
  width: 100%;
}
.r-v2-fmpc__selection,
.r-v2-fmpc__readonly {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--r-color-fg);
  min-width: 0;
}
.r-v2-fmpc__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-fmpc__placeholder {
  color: var(--r-color-fg-faint);
}
</style>
