<script setup lang="ts">
// VolumeControl — v2-native volume button + hover-revealed slider.
// Used in the soundtrack panel and mini-player. The shared
// `useSoundtrackPlayer` store owns volume / muted state; this widget
// is just a controller.
//
// The icon swaps between off / low / medium / high based on the
// current volume so the button reads as a level indicator at a
// glance. With a mouse the slider opens on hover and a click mutes;
// touch, keyboard and gamepad have no hover, so there the button opens
// the slider, which carries its own mute toggle.
import { RMenu, RSlider } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import { useInputModality } from "@/v2/composables/useInputModality";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";

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
const { modality } = useInputModality();
const hoverOpens = computed(() => modality.value === "mouse");
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
    :open-on-hover="hoverOpens"
    :close-on-content-click="false"
    location="top"
    :offset="6"
  >
    <template #activator="{ props: activatorProps }">
      <RBtn
        v-if="hoverOpens"
        v-bind="{ ...activatorProps, onClick: player.toggleMute }"
        :icon="icon"
        variant="text"
        :size="size"
        :aria-label="muteLabel"
      />
      <RBtn
        v-else
        v-bind="activatorProps"
        :icon="icon"
        variant="text"
        :size="size"
        :aria-label="t('rom.soundtrack-volume')"
      />
    </template>
    <div class="r-v2-volume">
      <RBtn
        :icon="icon"
        variant="text"
        size="small"
        :aria-label="muteLabel"
        :aria-pressed="muted"
        @click="player.toggleMute()"
      />
      <RSlider
        v-model="sliderValue"
        :min="0"
        :max="100"
        :step="1"
        color="primary"
        :aria-label="t('rom.soundtrack-volume')"
        class="r-v2-volume__slider"
      />
      <span class="r-v2-volume__value">{{ sliderValue }}</span>
    </div>
  </RMenu>
</template>

<style scoped>
.r-v2-volume {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  padding: var(--r-space-1) var(--r-space-4) var(--r-space-1) var(--r-space-1);
  min-width: 200px;
}
.r-v2-volume__slider {
  flex: 1;
  min-width: 120px;
}
.r-v2-volume__value {
  font-variant-numeric: tabular-nums;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  font-weight: var(--r-font-weight-semibold);
  min-width: 24px;
  text-align: right;
}
</style>
