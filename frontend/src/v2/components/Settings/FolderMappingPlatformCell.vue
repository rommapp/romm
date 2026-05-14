<script setup lang="ts">
// FolderMappingPlatformCell — editable Platform cell for the folder
// mappings table.
//
// Implementation: a plain `RSelect`. Conceptually this is what the
// cell is — pick one platform from a list — so a select reads more
// honestly than a button-activated menu, and we get the v2 select
// chrome (searchable header, themed scrollbar, identical paint to
// other selects) for free.
//
// `clearable` is wired up to the section's existing "remove mapping"
// flow: the X button only appears when the row already has a slug
// AND the row isn't auto-detected (auto rows clear by removing the
// binding, not by clicking the cell's X).
import { RIcon, RSelect } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";

type RowType = "alias" | "variant" | "auto" | null;

interface Row {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: RowType;
}

interface PlatformItem {
  slug: string;
  name: string;
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

const search = ref("");

const items = computed<PlatformItem[]>(() =>
  props.supportedPlatforms
    .map((p) => ({ slug: p.slug, name: p.display_name }))
    .sort((a, b) => a.name.localeCompare(b.name)),
);

const modelSlug = computed({
  get: () => props.row.slug ?? null,
  set: (next: string | null) => emit("select", next ?? undefined),
});
</script>

<template>
  <RSelect
    v-if="canEdit"
    v-model="modelSlug"
    v-model:search="search"
    :items="items"
    item-title="name"
    item-value="slug"
    searchable
    hide-details
    density="compact"
    variant="plain"
    :placeholder="t('common.select')"
    :search-placeholder="t('common.search')"
    class="r-v2-fmpc"
  >
    <!-- Read from `row` directly instead of the slot's `item` —
         when the row references a platform that isn't in
         `supportedPlatforms` (loading, removed, …), the slot's
         `item.raw` falls back to the raw slug string and the
         destructure crashes. `row.slug` + `row.displayName` are always
         coherent here because the section owns both. -->
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
    <template #item="{ props: itemProps, item }">
      <li v-bind="itemProps">
        <CachedPlatformIcon
          :slug="(item.raw as PlatformItem).slug"
          :name="(item.raw as PlatformItem).name"
          :size="20"
        />
        <span class="r-select__item-title">
          {{ (item.raw as PlatformItem).name }}
        </span>
      </li>
    </template>
  </RSelect>
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
/* Lock the field to the column's width — RSelect sizes its inner
   field to content by default, which would make each row's cell as
   wide as its platform name. The visible width then shifts as the
   user scrolls the table (different rows visible, different widths). */
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
