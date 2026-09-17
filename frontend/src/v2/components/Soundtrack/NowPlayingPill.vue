<script setup lang="ts">
// NowPlayingPill — the mini player's top-bar form on phones: a pill with the
// cover spinning inside a playback progress ring, the track title looping
// beside it, and play / pause plus next. The cover and title open the full
// mini player as a bottom sheet. On the narrowest screens the title steps
// aside while the scan indicator is up, so the bar never overflows.
import { RBtn, RMarquee, RMenu, RProgressCircular } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeScanning from "@/stores/scanning";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import NowPlayingCard from "@/v2/components/Soundtrack/NowPlayingCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useMiniPlayerVisible } from "@/v2/composables/useMiniPlayerVisible";
import { playerCoverUrl } from "@/v2/utils/soundtrackTracks";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const store = useSoundtrackPlayer();
const { track, meta, isPlaying, isBuffering, currentTime, duration, hasNext } =
  storeToRefs(store);
const { scanning } = storeToRefs(storeScanning());
const { xs } = useBreakpoint();
const visible = useMiniPlayerVisible();

const open = ref(false);
const coverUrl = computed(() => playerCoverUrl(meta.value));
const title = computed(() => meta.value.title || track.value?.fileName || "");
const showTitle = computed(() => !(xs.value && scanning.value));
const progress = computed(() =>
  duration.value > 0 ? (currentTime.value / duration.value) * 100 : 0,
);
</script>

<template>
  <div v-if="visible" class="r-v2-np-pill" v-bind="$attrs">
    <RMenu
      v-model="open"
      location="bottom end"
      :offset="8"
      width="380px"
      :close-on-content-click="false"
      content-class="r-v2-np-sheet"
      sheet-on-mobile
    >
      <template #activator="{ props: menuProps }">
        <RBtn
          v-bind="menuProps"
          variant="text"
          class="r-v2-np-pill__trigger"
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
          <RMarquee
            v-if="showTitle"
            :key="track?.fileId"
            class="r-v2-np-pill__title"
          >
            {{ title }}
          </RMarquee>
        </RBtn>
      </template>
      <NowPlayingCard />
    </RMenu>

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
  min-width: 0;
  padding: 1px 2px 1px 1px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-pill);
}

.r-v2-np-pill__trigger {
  min-width: 0 !important;
  height: auto !important;
  padding: 0 4px 0 0 !important;
  border-radius: var(--r-radius-pill) !important;
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

/* Shrinks before the bar overflows on the narrowest phones. */
.r-v2-np-pill__title {
  flex: 0 1 160px;
  font-size: var(--r-font-size-sm);
}
</style>

<style>
/* The card brings its own padding and ambient art edge to edge. */
.r-v2-np-sheet .r-menu__body {
  padding: 0;
}
</style>
