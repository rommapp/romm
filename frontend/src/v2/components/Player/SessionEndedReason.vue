<script setup lang="ts">
import { useI18n } from "vue-i18n";

defineProps<{ reason: string }>();

const { t } = useI18n();
</script>

<template>
  <div class="r-v2-session-ended-reason">
    <span class="r-v2-session-ended-reason__label">
      {{ t("play.session-ended-reason-label") }}
    </span>
    <span>{{ reason }}</span>
  </div>
</template>

<style scoped>
.r-v2-session-ended-reason {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow-wrap: anywhere;
}

.r-v2-session-ended-reason__label {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--r-color-fg-muted);
}
</style>
