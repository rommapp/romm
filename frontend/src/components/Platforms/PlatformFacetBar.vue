<script setup lang="ts">
// PlatformFacetBar: one multi-select per Platforms index facet. The view
// owns the URL-backed selection and the option counts.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RBtn, RIcon, RSelect } from "@/lib";
import type { FacetOption, PlatformFacetKey } from "@/utils/platformFacets";

defineOptions({ inheritAttrs: false });

export interface PlatformFacet {
  key: PlatformFacetKey;
  label: string;
  icon: string;
  options: FacetOption[];
  selected: readonly string[];
}

interface Props {
  facets: PlatformFacet[];
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "update", payload: { key: PlatformFacetKey; values: string[] }): void;
  (e: "clear"): void;
}>();

const { t } = useI18n();
// A long list (families on a big library) is easier to scan with a filter.
const SEARCHABLE_FROM = 8;

const hasSelection = computed(() =>
  props.facets.some((f) => f.selected.length > 0),
);

const optionTitle = (o: FacetOption) => `${o.label} (${o.count})`;
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-pfacets"
    role="group"
    :aria-label="t('platform.filter-platforms')"
  >
    <RSelect
      v-for="f in facets"
      :key="f.key"
      class="r-pfacets__select"
      :model-value="[...f.selected]"
      :items="f.options"
      :item-title="optionTitle"
      item-value="value"
      :placeholder="t('common.all')"
      :searchable="f.options.length >= SEARCHABLE_FROM"
      :disabled="!f.options.length"
      :data-facet="f.key"
      multiple
      clearable
      hide-details
      density="compact"
      prefix-label="stacked"
      @update:model-value="
        (v) => emit('update', { key: f.key, values: v as string[] })
      "
    >
      <template #prefix-label>
        <RIcon :icon="f.icon" size="14" />
        {{ f.label }}
      </template>
      <template #selection="{ item, index }">
        <span v-if="index > 0">,&nbsp;</span>
        <span>{{ (item.raw as FacetOption).label }}</span>
      </template>
    </RSelect>
    <RBtn
      v-if="hasSelection"
      variant="text"
      size="small"
      prepend-icon="mdi-filter-remove-outline"
      class="r-pfacets__clear"
      @click="emit('clear')"
    >
      {{ t("platform.reset-filters") }}
    </RBtn>
  </div>
</template>

<style scoped>
.r-pfacets {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  align-items: end;
  gap: var(--r-space-2);
  margin-bottom: var(--r-space-4);
}

.r-pfacets__select {
  min-width: 0;
}

html[data-bp~="sm-and-down"] .r-pfacets {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
html[data-bp~="sm-and-down"] .r-pfacets__clear {
  grid-column: 1 / -1;
  justify-self: start;
}
</style>
