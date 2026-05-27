<script setup lang="ts">
// BackBtn — pill-style "go back" button shared by gallery + detail
// topbars. Composes RIcon; not a design-system primitive (RBtn is), just a
// recurring feature pattern that three views use verbatim.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

interface Props {
  label?: string;
  to?: string | object;
}

const props = withDefaults(defineProps<Props>(), {
  label: "",
  to: undefined,
});

const { t } = useI18n();
const effectiveLabel = computed(() => props.label || t("common.back"));

defineEmits<{
  (e: "click", event: MouseEvent): void;
}>();

const tag = computed(() => (props.to ? "router-link" : "button"));
</script>

<template>
  <component
    :is="tag"
    v-bind="$attrs"
    :to="to"
    :type="tag === 'button' ? 'button' : undefined"
    class="back-btn"
    @click="(e: MouseEvent) => $emit('click', e)"
  >
    <RIcon icon="mdi-chevron-left" size="16" />
    <span>{{ effectiveLabel }}</span>
  </component>
</template>

<style scoped>
.back-btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-pill);
  padding: 5px 14px 5px 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  text-decoration: none;
  font-family: inherit;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}

.back-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
</style>
