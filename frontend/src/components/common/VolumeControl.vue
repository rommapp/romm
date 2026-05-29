<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";

withDefaults(
  defineProps<{
    btnSize?: "x-small" | "small" | "default" | "large";
  }>(),
  { btnSize: "small" },
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
  <v-menu
    :close-on-content-click="false"
    location="top"
    open-on-hover
    :open-delay="100"
    :close-delay="200"
    eager
    transition="false"
    class="transparent"
  >
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        :icon="icon"
        variant="text"
        :size="btnSize"
        @click="player.toggleMute()"
      />
    </template>
    <div
      class="volume-popup rounded-lg elevation-4 pa-2 mb-2 d-flex flex-column align-center bg-toplayer"
    >
      <span class="text-caption text-medium-emphasis mt-1">
        {{ sliderValue }}
      </span>
      <div
        class="volume-slider-wrap pt-2 d-flex justify-center overflow-hidden"
      >
        <v-slider
          v-model="sliderValue"
          :min="0"
          :max="100"
          :step="1"
          direction="vertical"
          density="compact"
          hide-details
          color="primary"
          thumb-size="14"
          track-size="3"
        />
      </div>
    </div>
  </v-menu>
</template>

<style scoped>
.volume-slider-wrap {
  height: 100px;
  width: 10px;
}

.volume-slider-wrap :deep(.v-slider) {
  height: 60px;
  min-height: 0;
}

.volume-slider-wrap :deep(.v-slider .v-input__control),
.volume-slider-wrap :deep(.v-slider .v-slider__container) {
  height: 60px;
  min-height: 0;
}
</style>
