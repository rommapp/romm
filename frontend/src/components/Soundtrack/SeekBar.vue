<script setup lang="ts">
// The track timeline shared by the soundtrack panel and the mini player: the
// elapsed and total time around a scrubber that advances smoothly.
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { usePlaybackTime } from "@/composables/usePlaybackTime";
import { RSlider } from "@/lib";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import { formatTrackTime } from "@/utils/time";

defineOptions({ inheritAttrs: false });

defineProps<{ disabled?: boolean }>();

const { t } = useI18n();
const store = useSoundtrackPlayer();
const { duration } = storeToRefs(store);
const playbackTime = usePlaybackTime();

// While dragging, the thumb follows the finger instead of the playback clock.
const dragTime = ref<number | null>(null);
const shownTime = computed(() => dragTime.value ?? playbackTime.value);

const valueText = computed(() =>
  t("rom.seek-progress", {
    current: formatTrackTime(shownTime.value),
    duration: formatTrackTime(duration.value),
  }),
);

function onSeek(value: number) {
  if (dragTime.value !== null) dragTime.value = value;
  store.seek(value);
}
</script>

<template>
  <div class="r-seek" v-bind="$attrs">
    <span class="r-seek__time">{{ formatTrackTime(shownTime) }}</span>
    <RSlider
      :model-value="shownTime"
      :max="duration || 0"
      :step="0.1"
      :disabled="disabled"
      color="primary"
      scrubber
      class="r-seek__slider"
      :aria-label="t('rom.soundtrack-seek')"
      :aria-valuetext="valueText"
      @start="(value: number) => (dragTime = value)"
      @end="dragTime = null"
      @update:model-value="onSeek"
    />
    <span class="r-seek__time r-seek__time--right">
      {{ formatTrackTime(duration) }}
    </span>
  </div>
</template>

<style scoped>
.r-seek {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  min-width: 0;
}

.r-seek__slider {
  flex: 1;
}

.r-seek__time {
  min-width: 36px;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}

.r-seek__time--right {
  text-align: right;
}
</style>
