<script setup lang="ts">
// VolumeControl — v2-native volume button + hover-revealed slider.
// Replaces the v1 VolumeControl (Vuetify `v-menu` + `v-slider`) used
// in the soundtrack panel and mini-player. The shared
// `useSoundtrackPlayer` store owns volume / muted state; this widget
// is just a controller.
//
// The icon swaps between off / low / medium / high based on the
// current volume so the button reads as a level indicator at a
// glance. Clicking the button toggles mute; the slider lives inside
// an `RMenu` opened on hover with a horizontal pill layout that
// matches v2's surface vocabulary (glass panel + brand-coloured fill).
import { RMenu, RSlider } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    size?: "x-small" | "small" | "default" | "large" | "x-large";
  }>(),
  { size: "small" },
);

const player = useSoundtrackPlayer();
const { volume, muted } = storeToRefs(player);

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
    open-on-hover
    :close-on-content-click="false"
    location="top"
    :offset="6"
  >
    <template #activator="{ props: activatorProps }">
      <RBtn
        v-bind="activatorProps"
        :icon="icon"
        variant="text"
        :size="size"
        :aria-label="muted ? 'Unmute' : 'Mute'"
        @click="player.toggleMute()"
      />
    </template>
    <div class="r-v2-volume">
      <RSlider
        v-model="sliderValue"
        :min="0"
        :max="100"
        :step="1"
        color="primary"
        aria-label="Volume"
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
  gap: 12px;
  padding: 10px 14px;
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
