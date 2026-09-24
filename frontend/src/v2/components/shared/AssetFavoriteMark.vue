<script setup lang="ts">
// The favorite heart on a save or state, for the surfaces that have no toggle
// to say it. Each surface places it: beside a save's name, over a state's
// screenshot.
import { RIcon } from "@v2/lib";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    favorite?: boolean;
    size?: number | string;
  }>(),
  { favorite: false, size: 14 },
);

const { t } = useI18n();
</script>

<template>
  <span
    v-if="favorite"
    class="r-asset-fav"
    role="img"
    :aria-label="t('rom.favorite')"
    :title="t('rom.favorite')"
    v-bind="$attrs"
  >
    <RIcon icon="mdi-heart" :size="size" />
  </span>
</template>

<style scoped>
.r-asset-fav {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}
</style>
