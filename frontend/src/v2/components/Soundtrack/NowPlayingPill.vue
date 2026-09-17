<script setup lang="ts">
// The mini player's top-bar form on phones: the cover in a progress ring plus
// previous, play / pause and next. The cover opens the full card as a sheet.
import { RBtn, RMenu, RProgressCircular } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import NowPlayingCard from "@/v2/components/Soundtrack/NowPlayingCard.vue";
import { useMiniPlayerVisible } from "@/v2/composables/useMiniPlayerVisible";
import { playerCoverUrl } from "@/v2/utils/soundtrackTracks";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const store = useSoundtrackPlayer();
const {
  meta,
  isPlaying,
  isBuffering,
  currentTime,
  duration,
  hasPrevious,
  hasNext,
} = storeToRefs(store);
const visible = useMiniPlayerVisible();

const coverUrl = computed(() => playerCoverUrl(meta.value));
const progress = computed(() =>
  duration.value > 0 ? (currentTime.value / duration.value) * 100 : 0,
);
</script>

<template>
  <div v-if="visible" class="r-v2-np-pill" v-bind="$attrs">
    <RMenu
      :close-on-content-click="false"
      content-class="r-v2-np-sheet"
      sheet-on-mobile
    >
      <template #activator="{ props: menuProps }">
        <RBtn
          v-bind="menuProps"
          :icon="true"
          variant="text"
          class="r-v2-np-pill__cover"
          :aria-label="t('rom.soundtrack-player')"
        >
          <RProgressCircular
            :indeterminate="isBuffering"
            :model-value="progress"
            :size="36"
            :width="2"
            color="primary"
          >
            <img
              :src="coverUrl"
              class="r-v2-np-pill__disc"
              :class="{ 'r-v2-np-pill__disc--spinning': isPlaying }"
              alt=""
            />
          </RProgressCircular>
        </RBtn>
      </template>
      <NowPlayingCard />
    </RMenu>

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
      variant="text"
      size="small"
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
  </div>
</template>

<style scoped>
/* Same pill surface as the user menu trigger beside it. */
.r-v2-np-pill {
  display: flex;
  align-items: center;
  height: var(--r-nav-pill-h);
  padding-inline-end: var(--r-space-1);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-pill);
}

.r-v2-np-pill__cover {
  width: 36px !important;
  height: 36px !important;
  border-radius: var(--r-radius-full) !important;
}

.r-v2-np-pill__disc {
  width: 28px;
  height: 28px;
  border-radius: var(--r-radius-full);
  object-fit: cover;
  animation: r-v2-np-pill-spin 8s linear infinite;
  animation-play-state: paused;
}

.r-v2-np-pill__disc--spinning {
  animation-play-state: running;
}

@keyframes r-v2-np-pill-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<style>
/* The card brings its own padding and ambient art edge to edge. */
.r-menu__panel.r-v2-np-sheet .r-menu__body {
  padding: 0;
}
</style>
