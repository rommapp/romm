<script setup lang="ts">
// Volume button whose icon reflects the level; a click opens a vertical slider
// with the level above it and a mute toggle below.
import { RBtn, RMenu, RSlider } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

withDefaults(
  defineProps<{
    size?: "x-small" | "small" | "default" | "large" | "x-large";
  }>(),
  { size: "small" },
);

const player = useSoundtrackPlayer();
const { volume, muted } = storeToRefs(player);
const muteLabel = computed(() =>
  muted.value ? t("rom.volume-unmute") : t("rom.volume-mute"),
);

const icon = computed(() => {
  if (muted.value || volume.value === 0) return "mdi-volume-off";
  if (volume.value < 0.34) return "mdi-volume-low";
  if (volume.value < 0.67) return "mdi-volume-medium";
  return "mdi-volume-high";
});

const sliderValue = computed({
  get: () => Math.round(volume.value * 100),
  set: (v: number) => player.setVolume(v / 100),
});
</script>

<template>
  <RMenu
    :close-on-content-click="false"
    location="top"
    :offset="6"
    content-class="r-v2-volume-menu"
  >
    <template #activator="{ props: activatorProps }">
      <RBtn
        v-bind="activatorProps"
        :icon="icon"
        variant="text"
        :size="size"
        :tooltip="t('rom.soundtrack-volume')"
        :aria-label="t('rom.soundtrack-volume')"
      />
    </template>
    <div class="r-v2-volume">
      <span class="r-v2-volume__value">{{ sliderValue }}</span>
      <RSlider
        v-model="sliderValue"
        :min="0"
        :max="100"
        :step="1"
        color="primary"
        vertical
        :aria-label="t('rom.soundtrack-volume')"
        class="r-v2-volume__slider"
      />
      <RBtn
        :icon="icon"
        variant="text"
        size="small"
        :aria-label="muteLabel"
        :aria-pressed="muted"
        @click="player.toggleMute()"
      />
    </div>
  </RMenu>
</template>

<style scoped>
.r-v2-volume {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--r-space-2);
  padding: var(--r-space-3) var(--r-space-1) var(--r-space-1);
}
.r-v2-volume__slider {
  height: 120px;
}
.r-v2-volume__value {
  font-variant-numeric: tabular-nums;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  font-weight: var(--r-font-weight-semibold);
}
</style>

<style>
/* A column this narrow sits under the menu's default 180px floor. The glass
   matches the top bar instead of the menu's panel tint. */
html .r-menu__panel.r-v2-volume-menu {
  min-width: 0;
  background: color-mix(in srgb, var(--r-color-bg) 78%, transparent);
  border-color: var(--r-color-border);
  backdrop-filter: blur(20px);
}
html.r-v2-reduced-motion .r-menu__panel.r-v2-volume-menu {
  background: var(--r-color-bg);
  backdrop-filter: none;
}
</style>
