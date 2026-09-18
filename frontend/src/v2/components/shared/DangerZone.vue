<script setup lang="ts">
// DangerZone — danger-tinted card that isolates a destructive action from
// the rest of a surface, so it never sits next to a primary button.
import { RIcon } from "@v2/lib";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

defineProps<{
  title: string;
  hint?: string;
}>();

defineSlots<{
  default(): unknown;
}>();

const { t } = useI18n();
</script>

<template>
  <section v-bind="$attrs" class="danger-zone">
    <header class="danger-zone__head">
      <RIcon icon="mdi-alert-outline" size="14" />
      <span>{{ t("common.danger-zone") }}</span>
    </header>
    <div class="danger-zone__row">
      <div class="danger-zone__copy">
        <p class="danger-zone__title">{{ title }}</p>
        <p v-if="hint" class="danger-zone__hint">{{ hint }}</p>
      </div>
      <slot />
    </div>
  </section>
</template>

<style scoped>
.danger-zone {
  padding: 14px;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 6%,
    transparent
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 35%, transparent);
  border-radius: var(--r-radius-md);
}

.danger-zone__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-status-base-danger);
}

.danger-zone__row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.danger-zone__copy {
  flex: 1;
  min-width: 0;
}

.danger-zone__title {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.danger-zone__hint {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}
</style>
