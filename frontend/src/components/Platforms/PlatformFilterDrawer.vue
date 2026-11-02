<script setup lang="ts">
// PlatformFilterDrawer: the Platforms index facets, laid out like the ROM
// gallery's FilterDrawer. The view owns the URL-backed selection and counts.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RBtn, RDrawer, RIcon, RSelect, RTag } from "@/lib";
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
  modelValue: boolean;
  facets: PlatformFacet[];
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "update", payload: { key: PlatformFacetKey; values: string[] }): void;
  (e: "clear"): void;
}>();

const { t } = useI18n();
// A long list (families on a big library) is easier to scan with a filter.
const SEARCHABLE_FROM = 8;

const activeCount = computed(
  () => props.facets.filter((f) => f.selected.length > 0).length,
);

const optionTitle = (o: FacetOption) => `${o.label} (${o.count})`;
</script>

<template>
  <RDrawer
    v-bind="$attrs"
    :model-value="modelValue"
    side="right"
    :width="440"
    icon="mdi-filter-variant"
    hide-close
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <template #header>
      <span>{{ t("platform.filters") }}</span>
      <RTag v-if="activeCount > 0" tone="brand" size="x-small">
        {{ activeCount }}
      </RTag>
    </template>

    <div class="r-pfd__rows">
      <RSelect
        v-for="f in facets"
        :key="f.key"
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
    </div>

    <template #footer>
      <RBtn
        variant="outlined"
        prepend-icon="mdi-restore"
        :disabled="activeCount === 0"
        @click="emit('clear')"
      >
        {{ t("platform.reset-filters") }}
      </RBtn>
      <div class="r-pfd__spacer" />
      <RBtn
        variant="flat"
        color="primary"
        @click="emit('update:modelValue', false)"
      >
        {{ t("common.close") }}
      </RBtn>
    </template>
  </RDrawer>
</template>

<style scoped>
.r-pfd__rows {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-pfd__spacer {
  flex: 1;
}
</style>
