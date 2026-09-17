<script setup lang="ts">
// NowPlayingButton — the mini player's top-bar form on phones: the cover in
// a playback progress ring next to play / pause. The cover opens the full
// mini player as a bottom sheet. While a scan shows its indicator on the
// narrowest screens, play / pause steps aside so the bar never overflows.
import { RBtn, RMenu, RProgressCircular } from "@v2/lib";
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
const { meta, isPlaying, isBuffering, currentTime, duration } =
  storeToRefs(store);
const { scanning } = storeToRefs(storeScanning());
const { xs } = useBreakpoint();
const visible = useMiniPlayerVisible();

const open = ref(false);
const coverUrl = computed(() => playerCoverUrl(meta.value));
const progress = computed(() =>
  duration.value > 0 ? (currentTime.value / duration.value) * 100 : 0,
);
</script>

<template>
  <div v-if="visible" class="r-v2-np-btn" v-bind="$attrs">
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
          :icon="true"
          variant="text"
          class="r-v2-np-btn__cover"
          :aria-label="t('rom.soundtrack-player')"
        >
          <RProgressCircular
            :indeterminate="isBuffering"
            :model-value="progress"
            :size="40"
            :width="2"
            color="primary"
          >
            <img :src="coverUrl" class="r-v2-np-btn__img" alt="" />
          </RProgressCircular>
        </RBtn>
      </template>
      <NowPlayingCard />
    </RMenu>

    <RBtn
      v-if="!(xs && scanning)"
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
  </div>
</template>

<style scoped>
.r-v2-np-btn {
  display: flex;
  align-items: center;
  gap: 2px;
}

.r-v2-np-btn__cover {
  border-radius: var(--r-radius-full);
}

.r-v2-np-btn__img {
  width: 32px;
  height: 32px;
  border-radius: var(--r-radius-full);
  object-fit: cover;
}
</style>

<style>
/* The card brings its own padding and ambient art edge to edge. */
.r-v2-np-sheet .r-menu__body {
  padding: 0;
}
</style>
