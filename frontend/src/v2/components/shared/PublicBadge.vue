<script setup lang="ts">
// The round globe over the thumbnail of something the user shared with other
// users: a screenshot, a save, a state. The caller positions it.
import { RIcon, RTooltip } from "@v2/lib";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <span class="r-public-badge" role="img" :aria-label="t('rom.public')">
    <RIcon icon="mdi-earth" size="13" />
    <RTooltip activator="parent" :text="t('rom.public')" location="top" />
  </span>
</template>

<style scoped>
.r-public-badge {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--r-color-overlay-scrim-strong);
  color: var(--r-color-overlay-fg);
}
</style>
