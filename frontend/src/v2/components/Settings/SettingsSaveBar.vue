<script setup lang="ts">
// SettingsSaveBar: sticky Discard/Save bar for a settings form with unsaved
// edits. Pad the page bottom ~72px so it never covers the last controls.
import { RBtn } from "@v2/lib";
import { useI18n } from "vue-i18n";

interface Props {
  visible: boolean;
  label: string;
  saving?: boolean;
  saveDisabled?: boolean;
}

withDefaults(defineProps<Props>(), {
  saving: false,
  saveDisabled: false,
});

const emit = defineEmits<{
  (e: "save"): void;
  (e: "discard"): void;
}>();

const { t } = useI18n();
</script>

<template>
  <Transition name="r-v2-settings-save-bar">
    <div v-if="visible" class="r-v2-settings-save-bar">
      <span class="r-v2-settings-save-bar__label">{{ label }}</span>
      <div class="r-v2-settings-save-bar__actions">
        <RBtn variant="text" :disabled="saving" @click="emit('discard')">
          {{ t("common.discard") }}
        </RBtn>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-content-save-outline"
          :loading="saving"
          :disabled="saveDisabled"
          @click="emit('save')"
        >
          {{ t("common.save") }}
        </RBtn>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.r-v2-settings-save-bar {
  position: sticky;
  bottom: 16px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 8px;
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  box-shadow: 0 12px 32px color-mix(in srgb, black 32%, transparent);
}
.r-v2-settings-save-bar__label {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-settings-save-bar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-v2-settings-save-bar-enter-active,
.r-v2-settings-save-bar-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-settings-save-bar-enter-from,
.r-v2-settings-save-bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-settings-save-bar-enter-from,
  .r-v2-settings-save-bar-leave-to {
    transform: none;
  }
}
</style>
