<script setup lang="ts">
// The round globe on something the user shared with other users. Over a
// thumbnail it sits on a scrim; `inline` tints it for plain surfaces, beside a
// title. The caller positions it. Private things carry no mark.
import { RIcon, RTooltip } from "@v2/lib";
import { useI18n } from "vue-i18n";

withDefaults(defineProps<{ inline?: boolean }>(), { inline: false });

const { t } = useI18n();
</script>

<template>
  <span
    class="r-public-badge"
    :class="{ 'r-public-badge--inline': inline }"
    role="img"
    :aria-label="t('common.public')"
  >
    <RIcon icon="mdi-earth" :size="inline ? 12 : 13" />
    <RTooltip activator="parent" :text="t('common.public')" location="top" />
  </span>
</template>

<style scoped>
.r-public-badge {
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--r-color-overlay-scrim-strong);
  color: var(--r-color-overlay-fg);
}
.r-public-badge--inline {
  width: 20px;
  height: 20px;
  background: color-mix(in srgb, var(--r-color-info) 16%, transparent);
  color: var(--r-color-info);
}
</style>
