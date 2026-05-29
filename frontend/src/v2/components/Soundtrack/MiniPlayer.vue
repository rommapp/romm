<script setup lang="ts">
// MiniPlayer — v2-native persistent soundtrack player.
//
// Owns the single app-wide `<audio>` element (the v1 mini-player used
// to own it). The shared `useSoundtrackPlayer` store binds to this
// element via `setAudioRef`; every other surface (the soundtrack
// panel inside GameDetails, the now-playing strip) reads through the
// store and drives playback by calling store methods. Keeping the
// audio element here means it survives route changes and the user
// can leave the soundtrack subtab without the music cutting out.
//
// The visible mini-card only paints when there's a track loaded AND
// the user isn't already on the full soundtrack panel — otherwise the
// two surfaces would race for the same playback affordance.
import { RBtn, RSlider, RSpinner } from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import type { Events } from "@/types/emitter";
import VolumeControl from "@/v2/components/Soundtrack/VolumeControl.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
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

// Generation token — bumped every time we reassign `src`. Any async
// `play()` promise resolves against the token current when it was
// kicked off, so stale awaits from prior tracks don't clobber the
// current state. Same idiom as v1's mini player.
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
  () =>
    meta.value.coverUrl ??
    meta.value.folderCoverUrl ??
    "/assets/default/album_cover.jpg",
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
      if (token !== loadToken) return;
      // Autoplay may be blocked; the user can hit play in the UI.
      // Don't surface a snackbar for that — real load failures come
      // through `@error`.
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
  // Snackbar payload still uses v1's `snackbarShow` event shape —
  // when v1 is removed, switch to `useSnackbar()` here.
  emitter?.emit("snackbarShow", {
    msg: t("rom.cant-play-track"),
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
  return t("rom.seek-progress", {
    current: fmt(v),
    duration: fmt(duration.value),
  });
}

function openRom() {
  if (!track.value) return;
  // Land on the soundtrack subtab directly so the full player takes
  // over — landing on Overview instead would leave the user one
  // extra click from the surface they were just driving via the
  // mini-player.
  router.push({
    name: "rom",
    params: { rom: track.value.romId },
    query: { tab: "media", subtab: "soundtrack" },
  });
}
</script>

<template>
  <!-- Persistent audio element — hidden, always mounted. -->
  <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
  <audio
    ref="audioEl"
    class="r-v2-mp__audio"
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

  <Transition name="r-v2-mp-slide">
    <div
      v-if="showMiniPlayer && track"
      class="r-v2-mp"
      role="region"
      :aria-label="t('rom.soundtrack-player')"
    >
      <!-- Top row: cover + meta + close/open-rom -->
      <div class="r-v2-mp__top">
        <div
          class="r-v2-mp__disc"
          :class="{ 'r-v2-mp__disc--spinning': isPlaying }"
          aria-hidden="true"
        >
          <img :src="coverUrl" class="r-v2-mp__disc-img" alt="" />
          <div v-if="isBuffering" class="r-v2-mp__disc-buffering">
            <RSpinner :size="20" :width="2" color="white" />
          </div>
        </div>

        <div class="r-v2-mp__meta">
          <div class="r-v2-mp__title" :title="meta.title || track.fileName">
            {{ meta.title || track.fileName }}
          </div>
          <div v-if="meta.artist" class="r-v2-mp__artist" :title="meta.artist">
            {{ meta.artist }}
          </div>
        </div>

        <div class="r-v2-mp__top-actions">
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

      <!-- Transport row: prev / play / next / volume -->
      <div class="r-v2-mp__transport">
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
          :icon="isPlaying ? 'mdi-pause-circle' : 'mdi-play-circle'"
          variant="text"
          size="large"
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
        <span class="r-v2-mp__transport-spacer" />
        <VolumeControl size="small" />
      </div>

      <!-- Seek row -->
      <div class="r-v2-mp__seek">
        <span class="r-v2-mp__time">{{ fmt(currentTime) }}</span>
        <RSlider
          :model-value="currentTime"
          :max="duration || 0"
          :step="0.1"
          color="primary"
          class="r-v2-mp__seek-slider"
          :aria-label="t('rom.soundtrack-seek')"
          :aria-valuetext="seekValueText(currentTime)"
          @update:model-value="(v: number) => store.seek(v)"
        />
        <span class="r-v2-mp__time r-v2-mp__time--right">
          {{ fmt(duration) }}
        </span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.r-v2-mp__audio {
  display: none;
}

.r-v2-mp {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: var(--r-z-toast, 2200);
  width: 380px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: var(--r-radius-lg);
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  color: var(--r-color-fg);
}

/* ── Top row ────────────────────────────────────────────────── */
.r-v2-mp__top {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.r-v2-mp__disc {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--r-color-bg);
  border: 1px solid var(--r-color-border);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px color-mix(in srgb, black 50%, transparent);
}
.r-v2-mp__disc-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  animation: r-v2-mp-spin 12s linear infinite;
  animation-play-state: paused;
}
.r-v2-mp__disc--spinning .r-v2-mp__disc-img {
  animation-play-state: running;
}
/* Static vinyl-record spindle — gives the rotation a fixed visual
   reference so the spin reads as motion rather than a flat circle. */
.r-v2-mp__disc::after {
  content: "";
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--r-color-bg);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, black 50%, transparent);
}
.r-v2-mp__disc-buffering {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 45%, transparent);
  z-index: 3;
}

@keyframes r-v2-mp-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-mp__disc-img {
    animation: none;
  }
}

.r-v2-mp__meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-v2-mp__title {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-mp__artist {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-mp__top-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

/* ── Transport row ──────────────────────────────────────────── */
.r-v2-mp__transport {
  display: flex;
  align-items: center;
  gap: 4px;
}
.r-v2-mp__transport-spacer {
  flex: 1;
}

/* ── Seek row ───────────────────────────────────────────────── */
.r-v2-mp__seek {
  display: flex;
  align-items: center;
  gap: 10px;
}
.r-v2-mp__seek-slider {
  flex: 1;
}
.r-v2-mp__time {
  font-variant-numeric: tabular-nums;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  min-width: 36px;
}
.r-v2-mp__time--right {
  text-align: right;
}

/* ── Enter / leave motion ───────────────────────────────────── */
.r-v2-mp-slide-enter-from,
.r-v2-mp-slide-leave-to {
  transform: translate(20%, 120%);
  opacity: 0;
}
.r-v2-mp-slide-enter-active,
.r-v2-mp-slide-leave-active {
  transition:
    transform 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s ease;
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-mp-slide-enter-active,
  .r-v2-mp-slide-leave-active {
    transition: opacity 0.2s ease;
  }
  .r-v2-mp-slide-enter-from,
  .r-v2-mp-slide-leave-to {
    transform: none;
  }
}
</style>
