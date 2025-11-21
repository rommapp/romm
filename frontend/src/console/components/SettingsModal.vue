<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import NavigationText from "@/console/components/NavigationText.vue";
import { useConsoleTheme } from "@/console/composables/useConsoleTheme";
import { useInputScope } from "@/console/composables/useInputScope";
import type { InputAction } from "@/console/input/actions";
import { getSfxEnabled, setSfxEnabled } from "@/console/utils/sfx";

const { t } = useI18n();
const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
}>();

const themeStore = useConsoleTheme();
const { subscribe } = useInputScope();

const selectedOption = ref(0);
const options = computed(() => [
  { label: "console.theme", type: "theme" as const },
  { label: "console.sound-effects", type: "sfx" as const },
]);

const themeOptions = [
  { value: "default", label: "Default" },
  { value: "neon", label: "Soft Neon" },
];

const sfxEnabled = ref(getSfxEnabled());

const selectedTheme = computed({
  get: () => themeStore.themeName,
  set: (value: string) => themeStore.setTheme(value),
});

const iconColor = computed(() => {
  const computedStyle = getComputedStyle(document.documentElement);
  return (
    computedStyle.getPropertyValue("--console-modal-header-bg").trim() ||
    "#000000"
  );
});

function closeModal() {
  emit("update:modelValue", false);
}

function handleAction(action: InputAction): boolean {
  if (!props.modelValue) return false;

  switch (action) {
    case "back":
      closeModal();
      return true;
    case "moveUp":
      selectedOption.value =
        (selectedOption.value - 1 + options.value.length) %
        options.value.length;
      return true;
    case "moveDown":
      selectedOption.value = (selectedOption.value + 1) % options.value.length;
      return true;
    case "moveLeft":
    case "moveRight": {
      const currentOption = options.value[selectedOption.value];
      if (currentOption.type === "theme") {
        const currentIndex = themeOptions.findIndex(
          (t) => t.value === selectedTheme.value,
        );
        const nextIndex =
          action === "moveLeft"
            ? (currentIndex - 1 + themeOptions.length) % themeOptions.length
            : (currentIndex + 1) % themeOptions.length;
        selectedTheme.value = themeOptions[nextIndex].value;
        return true;
      } else if (currentOption.type === "sfx") {
        sfxEnabled.value = !sfxEnabled.value;
        setSfxEnabled(sfxEnabled.value);
        return true;
      }
      return false;
    }
    default:
      return false;
  }
}

let off: (() => void) | null = null;

onMounted(() => {
  off = subscribe(handleAction);
});

onUnmounted(() => {
  off?.();
});

function getCurrentThemeLabel(): string {
  const theme = themeOptions.find((t) => t.value === selectedTheme.value);
  return theme?.label || "Default";
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    :width="600"
    scroll-strategy="block"
    no-click-animation
    persistent
    z-index="9999"
    scrim="black"
    class="lightbox-dialog"
  >
    <template #default>
      <div class="lightbox-header">
        <h2 class="text-h6" :style="{ color: 'var(--console-modal-text)' }">
          {{ t("console.console-settings") }}
        </h2>
        <v-btn
          icon="mdi-close"
          aria-label="Close"
          size="small"
          :color="iconColor"
          @click="closeModal"
        />
      </div>

      <div class="pa-6">
        <div class="settings-list">
          <div
            v-for="(option, index) in options"
            :key="option.type"
            class="settings-item"
            :class="{ 'settings-item-selected': selectedOption === index }"
          >
            <div class="settings-label">
              {{ t(option.label) }}
            </div>
            <div class="settings-value">
              <template v-if="option.type === 'theme'">
                <div class="theme-selector">
                  <span class="theme-indicator">‹</span>
                  <span class="theme-name">{{ getCurrentThemeLabel() }}</span>
                  <span class="theme-indicator">›</span>
                </div>
              </template>
              <template v-else-if="option.type === 'sfx'">
                <div class="sfx-toggle">
                  <span class="sfx-indicator">‹</span>
                  <span class="sfx-status">{{
                    sfxEnabled ? t("console.enabled") : t("console.disabled")
                  }}</span>
                  <span class="sfx-indicator">›</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <div class="lightbox-footer pa-4">
        <NavigationText
          :show-navigation="true"
          :show-select="false"
          :show-back="true"
          :show-toggle-favorite="false"
          :show-menu="false"
          :is-modal="true"
        />
      </div>
    </template>
  </v-dialog>
</template>

<style scoped>
.lightbox-dialog {
  backdrop-filter: blur(10px);
  cursor: none;
}

.lightbox-dialog :deep(.v-overlay__content) {
  max-height: 80vh;
  border: 1px solid var(--console-modal-border);
  background-color: var(--console-modal-bg);
  border-radius: 16px;
  animation: slideUp 0.3s ease;
  cursor: none;
}

.lightbox-dialog :deep(*) {
  cursor: none !important;
}

.lightbox-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  background-color: var(--console-modal-header-bg);
  border-bottom: 1px solid var(--console-modal-border-secondary);
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
}

.lightbox-footer {
  border-top: 1px solid var(--console-modal-border-secondary);
  background-color: var(--console-modal-header-bg);
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
}

.settings-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border: 2px solid transparent;
  border-radius: 12px;
  background-color: var(--console-modal-tile-bg);
  transition: all 0.2s ease;
}

.settings-item-selected {
  border-color: var(--console-modal-tile-selected-border);
  background-color: var(--console-modal-tile-selected-bg);
  box-shadow:
    0 0 0 2px var(--console-modal-tile-selected-border),
    0 0 16px var(--console-modal-tile-selected-border);
}

.settings-label {
  font-size: 1.1rem;
  font-weight: 500;
  color: var(--console-modal-text);
}

.settings-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.theme-selector,
.sfx-toggle {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  background-color: var(--console-modal-button-bg);
  border-radius: 8px;
  border: 1px solid var(--console-modal-button-border);
}

.theme-indicator,
.sfx-indicator {
  color: var(--console-modal-button-indicator);
  font-size: 1.2rem;
  font-weight: bold;
}

.theme-name,
.sfx-status {
  font-weight: 500;
  color: var(--console-modal-button-text);
  min-width: 80px;
  text-align: center;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
