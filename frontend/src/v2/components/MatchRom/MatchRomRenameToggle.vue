<script setup lang="ts">
// Rename-on-match toggle — shared between Split and Spotlight bodies.
//
// Replaces the old pill button: a card-shaped surface with a real
// switch on the right and an inline diff preview ("old.gba → new.gba")
// below. The card paints brand-tinted when the toggle is on so the
// effect is unambiguous; while off everything reads muted. Clicking
// anywhere on the card toggles, and the RSwitch carries the actual
// visual affordance.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import type { SimpleRom } from "@/stores/roms";
import RSwitch from "@/v2/lib/forms/RSwitch/RSwitch.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  rom: SimpleRom | null;
  matchedName: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const newName = computed(() => {
  if (!props.rom) return props.matchedName;
  return props.rom.fs_name.replace(
    props.rom.fs_name_no_tags,
    props.matchedName,
  );
});

function toggle() {
  if (props.disabled) return;
  emit("update:modelValue", !props.modelValue);
}
</script>

<template>
  <div
    class="rename-toggle"
    :class="{
      'rename-toggle--on': modelValue,
      'rename-toggle--disabled': disabled,
    }"
  >
    <button
      type="button"
      class="rename-toggle__head"
      :disabled="disabled"
      :aria-pressed="modelValue"
      @click="toggle"
    >
      <span class="rename-toggle__label">
        <RIcon icon="mdi-file-edit-outline" size="15" />
        <span>Rename file on disk</span>
      </span>
      <!-- Stop propagation so the switch click doesn't double-toggle
           via the parent button's handler. -->
      <RSwitch
        :model-value="modelValue"
        :disabled="disabled"
        size="small"
        @click.stop
        @update:model-value="emit('update:modelValue', $event)"
      />
    </button>

    <div v-if="rom" class="rename-toggle__preview">
      <code class="rename-toggle__name rename-toggle__name--old">
        {{ rom.fs_name }}
      </code>
      <RIcon icon="mdi-arrow-right" size="13" class="rename-toggle__arrow" />
      <code class="rename-toggle__name rename-toggle__name--new">
        {{ newName }}
      </code>
    </div>
  </div>
</template>

<style scoped>
.rename-toggle {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 14px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.rename-toggle--on {
  background: color-mix(
    in srgb,
    var(--r-color-brand-primary) 10%,
    var(--r-color-surface)
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    var(--r-color-border)
  );
}
.rename-toggle--disabled {
  opacity: 0.5;
  pointer-events: none;
}

.rename-toggle__head {
  appearance: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: transparent;
  border: none;
  padding: 0;
  font: inherit;
  color: var(--r-color-fg);
  cursor: pointer;
  text-align: left;
}
.rename-toggle__head:disabled {
  cursor: not-allowed;
}

.rename-toggle__label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.rename-toggle--on .rename-toggle__label {
  color: var(--r-color-brand-primary);
}

.rename-toggle__preview {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-family: var(--r-font-family-mono, ui-monospace, monospace);
  font-size: 11px;
}
.rename-toggle__name {
  padding: 3px 8px;
  border-radius: var(--r-radius-sm);
  background: color-mix(in srgb, var(--r-color-fg) 6%, transparent);
  color: var(--r-color-fg-muted);
  word-break: break-all;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.rename-toggle__arrow {
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.rename-toggle--on .rename-toggle__name--new {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  color: var(--r-color-fg);
}
.rename-toggle--on .rename-toggle__arrow {
  color: var(--r-color-brand-primary);
}
</style>
