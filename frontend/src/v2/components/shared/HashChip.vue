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
// The abbreviation is all that reaches the DOM, so when a copy cannot
// land the value would be unreachable. Clicking reveals the full string
// as selectable text instead: outside a secure context the clipboard
// API does not exist at all, so the click never attempts a copy, and a
// copy that fails for any other reason falls back to the same reveal.
//
// `compact` switches to the `x-small` size — useful for in-row
// hash clusters where vertical breathing room is tight. The trailing
// icon stays in both sizes so the click affordance is consistent.
import { RTag } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useClipboard } from "@/v2/composables/useClipboard";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    label: string;
    value: string | null;
    compact?: boolean;
  }>(),
  { compact: false },
);

const { t } = useI18n();
const clipboard = useClipboard();

const root = ref<HTMLButtonElement | null>(null);
const revealed = ref(false);

const shortened = computed(() => {
  if (!props.value) return "";
  if (props.value.length <= 14) return props.value;
  return `${props.value.substring(0, 6)}…${props.value.substring(
    props.value.length - 6,
  )}`;
});

const displayed = computed(() =>
  revealed.value ? (props.value ?? "") : shortened.value,
);

const appendIcon = computed(() => {
  if (revealed.value) return "mdi-eye-off-outline";
  return clipboard.isSupported ? "mdi-content-copy" : "mdi-eye-outline";
});

// Scoped to this chip so a selection made elsewhere on the page does not
// leave the collapse click dead.
function hasSelectionInside() {
  const selection = window.getSelection();
  if (!selection?.toString() || !selection.anchorNode) return false;
  return root.value?.contains(selection.anchorNode) ?? false;
}

async function copy() {
  if (!props.value) return;

  // Collapsing on the click that ends a drag-select would snatch the
  // value back the moment it was highlighted.
  if (revealed.value && hasSelectionInside()) return;

  if (!clipboard.isSupported) {
    revealed.value = !revealed.value;
    return;
  }

  const copied = await clipboard.copy(props.value, {
    successMessage: t("common.clipboard-copied", { label: props.label }),
  });
  if (!copied) revealed.value = true;
}
</script>

<template>
  <button
    v-if="value"
    ref="root"
    type="button"
    class="r-v2-hash-chip"
    :class="{ 'r-v2-hash-chip--revealed': revealed }"
    :title="`${label}: ${value}`"
    @click="copy"
  >
    <RTag
      :label="label"
      :text="displayed"
      :append-icon="appendIcon"
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

/* A revealed value exists to be selected by hand, so it opts back into
   text selection and wraps instead of widening the row past its
   container. */
.r-v2-hash-chip--revealed {
  cursor: text;
  user-select: text;
  max-width: 100%;
}
.r-v2-hash-chip--revealed:active {
  transform: none;
}
.r-v2-hash-chip--revealed :deep(.r-tag) {
  white-space: normal;
}
</style>
