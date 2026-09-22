<script setup lang="ts">
// What the owner marked on a save or state: the favorite heart and the labels.
// Kept apart from <AssetChips> so a phone can give the marks a band of their own.
import { RIcon, RTag } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Asset } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    asset: Asset;
    /** Off where a favorite toggle already shows the state (management). */
    showFavorite?: boolean;
  }>(),
  { showFavorite: true },
);

const { t } = useI18n();

const labels = computed(() => props.asset.labels ?? []);
const shown = computed(
  () => (props.showFavorite && props.asset.is_favorite) || labels.value.length,
);
</script>

<template>
  <span v-if="shown" class="r-asset-annotations" v-bind="$attrs">
    <span
      v-if="showFavorite && asset.is_favorite"
      class="r-asset-annotations__fav"
      role="img"
      :aria-label="t('rom.favorite')"
      :title="t('rom.favorite')"
    >
      <RIcon icon="mdi-heart" size="12" />
    </span>
    <RTag
      v-for="label in labels"
      :key="label"
      tone="info"
      size="x-small"
      prepend-icon="mdi-label-outline"
      :text="label"
    />
  </span>
</template>

<style scoped>
.r-asset-annotations {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  min-width: 0;
}
.r-asset-annotations__fav {
  display: inline-flex;
  align-items: center;
  color: var(--r-color-brand-primary);
}
</style>
