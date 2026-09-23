<script setup lang="ts">
// The select-all row above an owned save or state list. Always rendered so the
// checkbox stays put; only the actions appear once something is checked.
import { RBtn, RCheckbox } from "@v2/lib";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

defineProps<{
  count: number;
  total: number;
  allChecked: boolean;
  someChecked: boolean;
  /** Every checked item is already a favorite, so the heart clears them. */
  allFavorite: boolean;
}>();

const emit = defineEmits<{
  toggleAll: [];
  toggleFavorite: [];
  editLabels: [];
  delete: [];
  clear: [];
}>();

const { t } = useI18n();
</script>

<template>
  <div class="r-v2-asset-select" v-bind="$attrs">
    <RCheckbox
      class="r-v2-asset-select__all"
      :model-value="allChecked"
      :indeterminate="someChecked"
      size="sm"
      hide-details
      :label="
        count > 0
          ? t('rom.assets-selected-of', { selected: count, total })
          : t('rom.assets-count-n', total, { named: { n: total } })
      "
      @update:model-value="emit('toggleAll')"
    />

    <div v-if="count > 0" class="r-v2-asset-select__actions">
      <RBtn
        :icon="allFavorite ? 'mdi-heart' : 'mdi-heart-outline'"
        variant="text"
        size="small"
        :color="allFavorite ? 'primary' : undefined"
        :tooltip="
          allFavorite
            ? t('rom.remove-from-favorites')
            : t('rom.add-to-favorites')
        "
        :aria-label="
          allFavorite
            ? t('rom.remove-from-favorites')
            : t('rom.add-to-favorites')
        "
        @click="emit('toggleFavorite')"
      />
      <RBtn
        icon="mdi-label-outline"
        variant="text"
        size="small"
        :tooltip="t('rom.add-labels')"
        :aria-label="t('rom.add-labels')"
        @click="emit('editLabels')"
      />
      <RBtn
        icon="mdi-delete-outline"
        variant="text"
        color="romm-red"
        size="small"
        :tooltip="t('common.delete')"
        :aria-label="t('common.delete')"
        @click="emit('delete')"
      />
      <RBtn
        icon="mdi-close"
        variant="text"
        size="small"
        :tooltip="t('common.clear')"
        :aria-label="t('common.clear')"
        @click="emit('clear')"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-asset-select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 2px 4px;
  /* Holds the row's height so it does not jump when the actions appear. */
  min-height: 36px;
}
.r-v2-asset-select__all {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-asset-select__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
