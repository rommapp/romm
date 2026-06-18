<script setup lang="ts">
// HashChip — click-to-copy chip wrapping the shared RTag primitive so
// the visual matches MetadataTab's hash row and the rest of v2's
// `label + mono value` pills (single source of truth for tone, border,
// surface colour). Adds:
//   * a `<button>` shell so the click target is keyboard-accessible
//     and announced as interactive,
//   * a hover affordance via `:deep(.r-tag)`,
//   * value abbreviation (first 6…last 6) when long; the full
//     untruncated string is what we copy.
//
// `compact` switches to the `x-small` size — useful for in-row
// hash clusters where vertical breathing room is tight. The copy
// icon stays in both sizes so the click affordance is consistent.
import { RTag } from "@v2/lib";
import { computed } from "vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    label: string;
    value: string | null;
    compact?: boolean;
  }>(),
  { compact: false },
);

const snackbar = useSnackbar();

const shortened = computed(() => {
  if (!props.value) return "";
  if (props.value.length <= 14) return props.value;
  return `${props.value.substring(0, 6)}…${props.value.substring(
    props.value.length - 6,
  )}`;
});

async function copy() {
  if (!props.value) return;
  try {
    await navigator.clipboard.writeText(props.value);
    snackbar.success(`${props.label} copied to clipboard.`, {
      icon: "mdi-check-bold",
    });
  } catch {
    snackbar.error(`Couldn't copy ${props.label.toLowerCase()}.`, {
      icon: "mdi-close-circle",
    });
  }
}
</script>

<template>
  <button
    v-if="value"
    type="button"
    class="r-v2-hash-chip"
    :title="`${label}: ${value} (click to copy)`"
    @click="copy"
  >
    <RTag
      :label="label"
      :text="shortened"
      append-icon="mdi-content-copy"
      :size="compact ? 'x-small' : 'small'"
      mono
    />
  </button>
</template>

<style scoped>
/* The button is just the interactive shell — RTag owns the visuals.
   Stripping the native chrome so hover / focus styles can lean on
   the inner tag via :deep(). */
.r-v2-hash-chip {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  margin: 0;
  font: inherit;
  cursor: pointer;
  display: inline-flex;
  border-radius: var(--r-radius-chip);
  transition: transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-hash-chip:hover :deep(.r-tag) {
  border-color: var(--r-color-fg-muted);
  background: var(--r-color-surface-hover);
}
.r-v2-hash-chip:active {
  transform: scale(0.98);
}
</style>
