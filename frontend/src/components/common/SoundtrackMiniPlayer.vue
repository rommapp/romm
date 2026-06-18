<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import VolumeControl from "@/components/common/VolumeControl.vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import type { Events } from "@/types/emitter";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const store = useSoundtrackPlayer();
const {
  track,
  meta,
  isPlaying,
  isBuffering,
  currentTime,
  duration,
  hasPrevious,
  hasNext,
} = storeToRefs(store);

const audioEl = ref<HTMLAudioElement | null>(null);

// Generation token — bumped every time we reassign `src`. Any async `play()`
// promise resolves against the token that was current when it was kicked off,
// so stale awaits from prior tracks don't clobber the current state.
let loadToken = 0;

const onSoundtrackSubtab = computed(
  () =>
    route.name === "rom" &&
    route.query.tab === "media" &&
    route.query.subtab === "soundtrack",
);

const showMiniPlayer = computed(
  () => track.value !== null && !onSoundtrackSubtab.value,
);

const coverUrl = computed(
  () => meta.value.coverUrl ?? meta.value.folderCoverUrl ?? null,
);

onMounted(() => {
  store.setAudioRef(audioEl.value);
});

onBeforeUnmount(() => {
  store.setAudioRef(null);
});

watch(track, async (t) => {
  const el = audioEl.value;
  if (!el) return;
  const token = ++loadToken;
  if (t) {
    el.src = t.url;
    try {
      el.load();
    } catch {
      // ignore
    }
    try {
      await el.play();
    } catch {
      if (token !== loadToken) return; // a newer track has superseded this one
      // Autoplay may be blocked; user can click play in the UI. Don't surface
      // an error snackbar for that — real load failures come via `@error`.
    }
  } else {
    el.pause();
    el.removeAttribute("src");
    try {
      el.load();
    } catch {
      // ignore
    }
  }
});

function onPlay() {
  store.setPlaying(true);
  store.setBuffering(false);
}
function onPause() {
  store.setPlaying(false);
}
function onEnded() {
  store.setPlaying(false);
  if (hasNext.value) store.next();
}
function onTimeUpdate() {
  if (audioEl.value) store.reportCurrentTime(audioEl.value.currentTime || 0);
}
function onLoadedMetadata() {
  if (audioEl.value) store.setDuration(audioEl.value.duration || 0);
}
function onWaiting() {
  store.setBuffering(true);
}
function onCanPlay() {
  store.setBuffering(false);
}
function onError() {
  store.setError();
  emitter?.emit("snackbarShow", {
    msg: t("rom.soundtrack-playback-error"),
    icon: "mdi-alert",
    color: "red",
    timeout: 3000,
  });
}

function fmt(s: number) {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${sec}`;
}

function seekValueText(v: number): string {
  return `${fmt(v)} of ${fmt(duration.value)}`;
}
</script>

<template>
  <!-- Persistent (always-mounted) audio element, hidden visually -->
  <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
  <audio
    ref="audioEl"
    class="d-none"
    preload="metadata"
    aria-hidden="true"
    @play="onPlay"
    @pause="onPause"
    @ended="onEnded"
    @timeupdate="onTimeUpdate"
    @loadedmetadata="onLoadedMetadata"
    @waiting="onWaiting"
    @canplay="onCanPlay"
    @error="onError"
  />

  <Transition name="mini-player">
    <v-card
      v-if="showMiniPlayer && track"
      class="mini-player position-fixed elevation-12"
      role="region"
      :aria-label="t('rom.soundtrack-player')"
    >
      <div class="d-flex align-stretch pt-4 px-4 ga-3">
        <div
          class="mini-disc rounded-circle overflow-hidden d-flex align-center justify-center flex-shrink-0 align-self-center position-relative"
          :class="{ spinning: isPlaying }"
          aria-hidden="true"
        >
          <img v-if="coverUrl" :src="coverUrl" class="w-100 h-100" alt="" />
          <v-icon v-else size="40">mdi-music-note</v-icon>
          <div
            v-if="isBuffering"
            class="buffering-overlay position-absolute d-flex align-center justify-center"
          >
            <v-progress-circular
              indeterminate
              size="24"
              width="2"
              color="white"
            />
          </div>
        </div>
        <div class="d-flex flex-column flex-grow-1" style="min-width: 0">
          <div class="d-flex align-center">
            <div class="flex-grow-1" style="min-width: 0">
              <div class="text-body-2 text-truncate">
                {{ meta.title || track.fileName }}
              </div>
              <div
                v-if="meta.artist"
                class="text-subtitle-2 text-medium-emphasis text-truncate"
              >
                {{ meta.artist }}
              </div>
            </div>
            <v-btn
              icon="mdi-open-in-new"
              variant="text"
              size="small"
              :aria-label="t('rom.soundtrack-open-rom')"
              @click="
                router.push({ name: 'rom', params: { rom: track.romId } })
              "
            />
            <v-btn
              icon="mdi-close"
              variant="text"
              size="small"
              :aria-label="t('rom.soundtrack-close-player')"
              @click="store.stop()"
            />
          </div>
          <div class="d-flex align-center ga-1 mt-auto">
            <v-btn
              icon="mdi-skip-previous"
              variant="text"
              size="small"
              :disabled="!hasPrevious"
              :aria-label="t('rom.soundtrack-previous')"
              @click="store.previous()"
            />
            <v-btn
              :icon="isPlaying ? 'mdi-pause-circle' : 'mdi-play-circle'"
              variant="text"
              size="default"
              :aria-label="
                isPlaying ? t('rom.soundtrack-pause') : t('rom.soundtrack-play')
              "
              @click="store.togglePlayPause()"
            />
            <v-btn
              icon="mdi-skip-next"
              variant="text"
              size="small"
              :disabled="!hasNext"
              :aria-label="t('rom.soundtrack-next')"
              @click="store.next()"
            />
            <v-divider vertical class="mx-1 my-2" />
            <VolumeControl btn-size="small" />
          </div>
        </div>
      </div>
      <div class="d-flex align-center px-4 pb-2 ga-2">
        <span class="text-caption text-medium-emphasis">
          {{ fmt(currentTime) }}
        </span>
        <v-slider
          :model-value="currentTime"
          :max="duration || 0"
          :step="0.1"
          density="compact"
          hide-details
          color="primary"
          thumb-size="12"
          track-size="2"
          class="flex-grow-1"
          :aria-label="t('rom.soundtrack-seek')"
          :aria-valuetext="seekValueText(currentTime)"
          @update:model-value="(v: number) => store.seek(v)"
        />
        <span class="text-caption text-medium-emphasis">
          {{ fmt(duration) }}
        </span>
      </div>
    </v-card>
  </Transition>
</template>

<style scoped>
.mini-player {
  bottom: 16px;
  right: 16px;
  width: 360px;
  max-width: calc(100vw - 32px);
  z-index: 2000;
  border-radius: 12px;
  background: rgba(var(--v-theme-toplayer), 0.98);
  backdrop-filter: blur(8px);
}

.mini-disc {
  width: 88px;
  height: 88px;
  background: rgba(0, 0, 0, 0.25);
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.6);
}
.mini-disc img {
  object-fit: cover;
  animation: spin 12s linear infinite;
  animation-play-state: paused;
}
.mini-disc.spinning img {
  animation-play-state: running;
}
.buffering-overlay {
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .mini-disc img,
  .mini-disc.spinning img {
    animation: none;
  }
}

.mini-player-enter-from,
.mini-player-leave-to {
  transform: translate(20%, 120%);
  opacity: 0;
}
.mini-player-enter-active,
.mini-player-leave-active {
  transition:
    transform 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s ease;
}
@media (prefers-reduced-motion: reduce) {
  .mini-player-enter-active,
  .mini-player-leave-active {
    transition: opacity 0.2s ease;
  }
  .mini-player-enter-from,
  .mini-player-leave-to {
    transform: none;
  }
}
</style>
