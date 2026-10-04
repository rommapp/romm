<script setup lang="ts">
// RSectionLabel: the small uppercase label that heads a section or a field group.
// `as` keeps the call site's element; spacing around it belongs to the caller.
import RIcon from "../RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  as?: string;
  size?: "sm" | "md";
  tone?: "muted" | "faint" | "secondary";
  icon?: string | undefined;
}

withDefaults(defineProps<Props>(), {
  as: "div",
  size: "md",
  tone: "muted",
  icon: undefined,
});
</script>

<template>
  <component
    :is="as"
    v-bind="$attrs"
    class="r-section-label"
    :class="[`r-section-label--${size}`, `r-section-label--${tone}`]"
  >
    <RIcon v-if="icon" :icon="icon" class="r-section-label__icon" />
    <span class="r-section-label__text"><slot /></span>
  </component>
</template>

<style scoped>
.r-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  line-height: 1.4;
  text-transform: uppercase;
}
.r-section-label--md {
  font-size: 12px;
}
.r-section-label--sm {
  font-size: var(--r-font-size-xs);
}
.r-section-label--muted {
  color: var(--r-color-fg-muted);
}
.r-section-label--faint {
  color: var(--r-color-fg-faint);
}
.r-section-label--secondary {
  color: var(--r-color-fg-secondary);
}

/* Whole-pixel glyph sizes keep the icon crisp; the md lift offsets the
   descender room in the line box so the icon centres on the capitals. */
.r-section-label--md .r-section-label__icon {
  position: relative;
  top: -1px;
  font-size: 14px;
}
.r-section-label--sm .r-section-label__icon {
  font-size: 12px;
}

.r-section-label__text {
  min-width: 0;
}
</style>
