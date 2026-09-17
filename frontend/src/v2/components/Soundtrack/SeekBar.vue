<script setup lang="ts">
// The track timeline shared by the soundtrack panel and the mini player: the
// elapsed and total time around a scrubber that advances smoothly.
import { RSlider } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import { usePlaybackTime } from "@/v2/composables/usePlaybackTime";
import { formatTrackTime } from "@/v2/utils/time";

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
  <div class="r-v2-seek" v-bind="$attrs">
    <span class="r-v2-seek__time">{{ formatTrackTime(shownTime) }}</span>
    <RSlider
      :model-value="shownTime"
      :max="duration || 0"
      :step="0.1"
      :disabled="disabled"
      color="primary"
      scrubber
      class="r-v2-seek__slider"
      :aria-label="t('rom.soundtrack-seek')"
      :aria-valuetext="valueText"
      @start="(value: number) => (dragTime = value)"
      @end="dragTime = null"
      @update:model-value="onSeek"
    />
    <span class="r-v2-seek__time r-v2-seek__time--right">
      {{ formatTrackTime(duration) }}
    </span>
  </div>
</template>

<style scoped>
.r-v2-seek {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  min-width: 0;
}

.r-v2-seek__slider {
  flex: 1;
}

.r-v2-seek__time {
  min-width: 36px;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}

.r-v2-seek__time--right {
  text-align: right;
}
</style>
