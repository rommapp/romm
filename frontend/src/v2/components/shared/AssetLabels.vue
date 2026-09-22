<script setup lang="ts">
// A save or state's labels, as chips. The favorite heart is separate
// (<AssetFavoriteMark>) because each surface places it differently.
import { RTag } from "@v2/lib";
import { computed } from "vue";
import type { Asset } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ asset: Asset }>();

const labels = computed(() => props.asset.labels ?? []);
</script>

<template>
  <span v-if="labels.length" class="r-asset-labels" v-bind="$attrs">
    <RTag
      v-for="label in labels"
      :key="label"
      tone="info"
      size="x-small"
      :text="label"
    />
  </span>
</template>

<style scoped>
.r-asset-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  min-width: 0;
}
</style>
