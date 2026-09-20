<script setup lang="ts">
// ProviderBadges: the metadata providers a ROM matched, as tooltipped
// logo chips. Rendered twice by GameListRow (the column layout's title cell
// and the compact row's detail panel), so it lives here rather than twice
// in that template.
import { RTooltip } from "@v2/lib";
import type { MetadataProvider } from "@/v2/utils/metadataProviders";

defineProps<{ providers: readonly MetadataProvider[] }>();
</script>

<template>
  <span class="provider-badges">
    <span
      v-for="provider in providers"
      :key="provider.key"
      class="provider-badges__item"
      :style="provider.bg ? { background: provider.bg } : undefined"
    >
      <img
        :src="`/assets/scrappers/${provider.logo}`"
        :alt="provider.title"
        width="14"
        height="14"
      />
      <RTooltip activator="parent" :text="provider.title" location="top" />
    </span>
  </span>
</template>

<style scoped>
.provider-badges {
  display: flex;
  align-items: center;
  gap: 3px;
  overflow: hidden;
}

.provider-badges__item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: var(--r-color-surface);
  flex-shrink: 0;
}

.provider-badges__item img {
  display: block;
  object-fit: contain;
}
</style>
