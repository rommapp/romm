<script setup lang="ts">
// The mini player's body in the soundtrack header's look. Floats in a corner on
// desktop and opens as a sheet from the top bar on phones.
import { RBtn, RSlider, RSpinner } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import AmbientArt from "@/v2/components/Soundtrack/AmbientArt.vue";
import NowPlayingChips from "@/v2/components/Soundtrack/NowPlayingChips.vue";
import VolumeControl from "@/v2/components/Soundtrack/VolumeControl.vue";
import { nowPlayingCaption, playerCoverUrl } from "@/v2/utils/soundtrackTracks";
import { formatTrackTime } from "@/v2/utils/time";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const router = useRouter();
const store = useSoundtrackPlayer();
const {
  track,
  meta,
  playlist,
  isPlaying,
  isBuffering,
  currentTime,
  duration,
  hasPrevious,
  hasNext,
  isShuffled,
} = storeToRefs(store);

const coverUrl = computed(() => playerCoverUrl(meta.value));
const title = computed(() => meta.value.title || track.value?.fileName || "");
const caption = computed(() => nowPlayingCaption(meta.value));
const position = computed(() => {
  const active = track.value;
  if (!active) return 0;
  return (
    playlist.value.findIndex(
      (entry) => entry.fileId === active.fileId && entry.romId === active.romId,
    ) + 1
  );
});

function seekValueText(v: number): string {
  return t("rom.seek-progress", {
    current: formatTrackTime(v),
    duration: formatTrackTime(duration.value),
  });
}

function openRom() {
  if (!track.value) return;
  // Straight to the Soundtrack subtab, where the full player takes over.
  router.push({
    name: ROUTES.ROM,
    params: { rom: track.value.romId },
    query: { tab: "media", subtab: "soundtrack" },
  });
}
</script>

<template>
  <div
    class="r-v2-np-card"
    role="region"
    :aria-label="t('rom.soundtrack-player')"
    v-bind="$attrs"
  >
    <AmbientArt :url="coverUrl" />

    <div class="r-v2-np-card__head">
      <div class="r-v2-np-card__cover">
        <img :src="coverUrl" class="r-v2-np-card__cover-img" alt="" />
        <div
          v-if="isBuffering"
          class="r-v2-np-card__buffering"
          aria-hidden="true"
        >
          <RSpinner :size="24" :width="2" color="white" />
        </div>
      </div>

      <div class="r-v2-np-card__text">
        <p class="r-v2-np-card__title" :title="title">{{ title }}</p>
        <p class="r-v2-np-card__caption" :title="caption">{{ caption }}</p>
        <NowPlayingChips
          :key="track?.fileId"
          :tags="meta"
          :position="position"
          :total="playlist.length"
        />
      </div>

      <div class="r-v2-np-card__actions">
        <RBtn
          icon="mdi-open-in-new"
          variant="text"
          size="small"
          :tooltip="t('rom.soundtrack-open-rom-tooltip')"
          :aria-label="t('rom.soundtrack-open-rom-tooltip')"
          @click="openRom"
        />
        <RBtn
          icon="mdi-close"
          variant="text"
          size="small"
          :tooltip="t('rom.soundtrack-close-player')"
          :aria-label="t('rom.soundtrack-close-player')"
          @click="store.stop()"
        />
      </div>
    </div>

    <div class="r-v2-np-card__transport">
      <RBtn
        icon="mdi-shuffle"
        :variant="isShuffled ? 'translucent' : 'text'"
        size="small"
        :color="isShuffled ? 'primary' : undefined"
        :aria-pressed="isShuffled"
        :tooltip="t('common.shuffle')"
        :aria-label="t('common.shuffle')"
        @click="store.toggleShuffle()"
      />
      <RBtn
        icon="mdi-skip-previous"
        variant="text"
        size="small"
        :disabled="!hasPrevious"
        :tooltip="t('rom.soundtrack-previous')"
        :aria-label="t('rom.soundtrack-previous')"
        @click="store.previous()"
      />
      <RBtn
        :icon="isPlaying ? 'mdi-pause' : 'mdi-play'"
        variant="flat"
        color="primary"
        class="r-v2-np-card__play"
        :tooltip="
          isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
        "
        :aria-label="
          isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
        "
        @click="store.togglePlayPause()"
      />
      <RBtn
        icon="mdi-skip-next"
        variant="text"
        size="small"
        :disabled="!hasNext"
        :tooltip="t('rom.soundtrack-next')"
        :aria-label="t('rom.soundtrack-next')"
        @click="store.next()"
      />
      <VolumeControl size="small" />
    </div>

    <div class="r-v2-np-card__seek">
      <span class="r-v2-np-card__time">{{ formatTrackTime(currentTime) }}</span>
      <RSlider
        :model-value="currentTime"
        :max="duration || 0"
        :step="0.1"
        color="primary"
        class="r-v2-np-card__slider"
        :aria-label="t('rom.soundtrack-seek')"
        :aria-valuetext="seekValueText(currentTime)"
        @update:model-value="(v: number) => store.seek(v)"
      />
      <span class="r-v2-np-card__time r-v2-np-card__time--right">
        {{ formatTrackTime(duration) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.r-v2-np-card {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding: var(--r-space-4);
  color: var(--r-color-fg);
}

.r-v2-np-card__head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--r-space-3);
  align-items: start;
}

.r-v2-np-card__cover {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  border: 1px solid var(--r-color-border);
}

.r-v2-np-card__cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.r-v2-np-card__buffering {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 45%, transparent);
}

.r-v2-np-card__text {
  align-self: center;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

/* One line each, reserved even when empty, so the card never resizes. */
.r-v2-np-card__title,
.r-v2-np-card__caption {
  margin: 0;
  min-height: 1lh;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-np-card__title {
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  line-height: var(--r-line-height-tight);
}

.r-v2-np-card__caption {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-np-card__actions {
  display: flex;
  gap: 2px;
}

.r-v2-np-card__transport {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--r-space-1);
}

.r-v2-np-card__play {
  border-radius: var(--r-radius-full);
}

.r-v2-np-card__seek {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
}

.r-v2-np-card__slider {
  flex: 1;
}

.r-v2-np-card__time {
  min-width: 36px;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}

.r-v2-np-card__time--right {
  text-align: right;
}
</style>
