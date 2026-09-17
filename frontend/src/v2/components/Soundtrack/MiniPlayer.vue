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
// The visible card floats in a corner on desktop; on phones the top bar's
// NowPlayingButton opens the same card as a sheet instead.
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import type { Events } from "@/types/emitter";
import NowPlayingCard from "@/v2/components/Soundtrack/NowPlayingCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useMiniPlayerVisible } from "@/v2/composables/useMiniPlayerVisible";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const store = useSoundtrackPlayer();
const { track, hasNext } = storeToRefs(store);
const { smAndDown } = useBreakpoint();
const visible = useMiniPlayerVisible();

const audioEl = ref<HTMLAudioElement | null>(null);

// Generation token — bumped every time we reassign `src`. Any async
// `play()` promise resolves against the token current when it was
// kicked off, so stale awaits from prior tracks don't clobber the
// current state. Same idiom as v1's mini player.
let loadToken = 0;

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
