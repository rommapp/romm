<script setup lang="ts">
// Owns the app-wide `<audio>` element and chiptune engine, so playback survives
// route changes. The card floats on desktop; on phones the top bar's
// NowPlayingPill opens it.
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import storePlaying from "@/stores/playing";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import type { Events } from "@/types/emitter";
import NowPlayingCard from "@/v2/components/Soundtrack/NowPlayingCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useMiniPlayerVisible } from "@/v2/composables/useMiniPlayerVisible";
import { ChiptunePlayer } from "@/v2/utils/chiptunePlayer";
import { isChiptuneFile } from "@/v2/utils/soundtrackTracks";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const store = useSoundtrackPlayer();
const { track, hasNext } = storeToRefs(store);
const { smAndDown } = useBreakpoint();
const visible = useMiniPlayerVisible();
const playingStore = storePlaying();

const audioEl = ref<HTMLAudioElement | null>(null);
let chiptune: ChiptunePlayer | null = null;
// Whichever of the two is playing the current track. Events from the other
// are dropped, since pausing one while the other starts fires out of order.
let active: HTMLAudioElement | ChiptunePlayer | null = null;

// On phones the mini player lives in the top bar, which a running game hides,
// so the music pauses rather than play on with no controls.
watch([() => playingStore.stageActive, smAndDown], ([stage, phone]) => {
  if (stage && phone) active?.pause();
});

// Generation token — bumped every time we reassign `src`. Any async
// `play()` promise resolves against the token current when it was
// kicked off, so stale awaits from prior tracks don't clobber the
// current state. Same idiom as v1's mini player.
let loadToken = 0;

// Track loads, seeks and short stalls often resolve within a second; buffering
// is only reported once a wait outlasts that, so the covers don't flash.
const BUFFERING_DELAY_MS = 1000;
let bufferingTimer: ReturnType<typeof setTimeout> | undefined;

function setBuffered() {
  clearTimeout(bufferingTimer);
  store.setBuffering(false);
}

function scheduleBuffering() {
  clearTimeout(bufferingTimer);
  bufferingTimer = setTimeout(
    () => store.setBuffering(true),
    BUFFERING_DELAY_MS,
  );
}

function getChiptune(): ChiptunePlayer {
  if (chiptune) return chiptune;
  const player = new ChiptunePlayer();
  player.addEventListener("play", onPlay);
  player.addEventListener("pause", onPause);
  player.addEventListener("ended", onEnded);
  player.addEventListener("timeupdate", onTimeUpdate);
  player.addEventListener("loadedmetadata", onLoadedMetadata);
  player.addEventListener("canplay", onCanPlay);
  player.addEventListener("error", onError);
  chiptune = player;
  return player;
}

function activate(sink: HTMLAudioElement | ChiptunePlayer) {
  active = sink;
  store.setAudioRef(sink);
}

function unloadAudio(el: HTMLAudioElement) {
  el.pause();
  el.removeAttribute("src");
  try {
    el.load();
  } catch {
    // ignore
  }
}

onMounted(() => {
  if (audioEl.value) activate(audioEl.value);
});

onBeforeUnmount(() => {
  clearTimeout(bufferingTimer);
  store.setAudioRef(null);
  chiptune?.close();
});

watch(track, async (t) => {
  const el = audioEl.value;
  if (!el) return;
  const token = ++loadToken;
  if (!t) {
    setBuffered();
    unloadAudio(el);
    chiptune?.unload();
    return;
  }

  // The store flags a new track as buffering; hold that back like any wait.
  store.setBuffering(false);
  scheduleBuffering();
  let sink: HTMLAudioElement | ChiptunePlayer;
  // Catalog tracks carry a display title as `fileName`; the stream URL always
  // ends in the real file name.
  if (isChiptuneFile(new URL(t.url, window.location.href).pathname)) {
    unloadAudio(el);
    sink = getChiptune();
    activate(sink);
    void sink.load(t.url);
  } else {
    chiptune?.unload();
    sink = el;
    activate(sink);
    el.src = t.url;
    try {
      el.load();
    } catch {
      // ignore
    }
  }
  try {
    await sink.play();
  } catch {
    if (token !== loadToken) return;
    // Autoplay may be blocked; the user can hit play in the UI. Real load
    // failures come through `error` events, so no snackbar here.
  }
});

function isActive(event: Event): boolean {
  return event.target === active;
}

function onPlay(event: Event) {
  if (!isActive(event)) return;
  store.setPlaying(true);
  setBuffered();
}
function onPause(event: Event) {
  if (!isActive(event)) return;
  store.setPlaying(false);
}
function onEnded(event: Event) {
  if (!isActive(event)) return;
  store.setPlaying(false);
  if (hasNext.value) store.next();
}
function onTimeUpdate(event: Event) {
  if (!isActive(event) || !active) return;
  store.reportCurrentTime(active.currentTime || 0);
}
function onLoadedMetadata(event: Event) {
  if (!isActive(event) || !active) return;
  store.setDuration(active.duration || 0);
}
function onWaiting(event: Event) {
  if (!isActive(event)) return;
  scheduleBuffering();
}
function onCanPlay(event: Event) {
  if (!isActive(event)) return;
  setBuffered();
}
function onError(event: Event) {
  if (!isActive(event)) return;
  clearTimeout(bufferingTimer);
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
    <div v-if="visible && !smAndDown" class="r-v2-mp">
      <NowPlayingCard />
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
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: var(--r-radius-lg);
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  backdrop-filter: blur(28px);
  overflow: hidden;
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
