<script setup lang="ts">
// Player for the emulator streaming framework. A native
// emulator (PCSX2 / Dolphin / xemu / Eden) runs in a separate container
// with a Selkies WebRTC stream. RomM claims a session through the
// backend `/api/streaming` endpoints and displays the stream in an
// iframe pointed at the container's web UI. Session lifecycle, save
// state control, and volume are proxied to a broker sidecar inside
// that container via the shared `useStreamingStore`.
//
// Layout — two states, mirroring the Ruffle/EmulatorJS players:
//   1. Launch screen: hero cover + title + Play CTA + back links, plus
//      an in-use / error alert when the session can't be claimed.
//   2. Active player: full-bleed iframe with an auto-hiding control
//      bar (volume, save/load state, fullscreen, save-and-exit, stop).
//
// The streaming store owns the session state. This view only owns the
// local player chrome (UI visibility, fullscreen, pending flags).
import { RAlert, RBtn, RIcon, RSpinner } from "@v2/lib";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import streamingApi from "@/services/api/streaming";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import { useStreamingStore } from "@/stores/streaming";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

type PlayerState = "idle" | "loading" | "playing" | "error" | "exited";
type ErrorType =
  "occupied" | "not_configured" | "rom_not_found" | "server" | null;

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const streamingStore = useStreamingStore();
const snackbar = useSnackbar();
const setBgArt = useBackgroundArt();

const romsStore = storeRoms();
const galleryRoms = storeGalleryRoms();
const playingStore = storePlaying();
const playSession = usePlaySession();

const rom = ref<DetailedRom | null>(null);
const playerState = ref<PlayerState>("idle");
const errorType = ref<ErrorType>(null);
const errorMessage = ref<string>("");
const occupiedBy = ref<{ rom_name: string; claimed_at: string } | null>(null);
const containerHost = ref<string>("");
const isFullscreen = ref(false);
const isUIVisible = ref(true);
const isSavingAndExiting = ref(false);
const isSavingState = ref(false);
const isLoadingState = ref(false);
const isLoadingAutosave = ref(false);
const selectedSlot = ref(1);
const volume = ref(1);
const isMuted = ref(false);

const playerWrapper = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);

const romId = computed(() => Number(route.params.rom));

// Seed synchronously so the hero cover is in the DOM when the view
// transition captures this view and the morph pairs on entry. From
// GameDetails the full DetailedRom is in `currentRom`; on a direct
// gallery→play only a SimpleRom exists, so seed a cover-only `heroSeed`
// (`rom` stays null until `onMounted` refetches). See EmulatorJS / Ruffle
// for the same pattern.
if (romsStore.currentRom && romsStore.currentRom.id === romId.value) {
  rom.value = romsStore.currentRom;
}

const heroSeed = ref<SimpleRom | null>(null);
if (!rom.value && romId.value != null) {
  heroSeed.value = galleryRoms.getRomById(romId.value);
}

const heroRom = computed<DetailedRom | SimpleRom | null>(
  () => rom.value ?? heroSeed.value,
);

const container = computed(() =>
  rom.value
    ? streamingStore.containerForPlatform(rom.value.platform_slug)
    : null,
);

const capabilities = computed(() =>
  streamingStore.platformCapabilities(rom.value?.platform_slug),
);

// If the platform changes mid-session and the new one has fewer slots,
// clamp selectedSlot so we never send an out-of-range value to the broker.
watch(
  () => capabilities.value.maxSlots,
  (max) => {
    if (selectedSlot.value > max) selectedSlot.value = 1;
  },
);

const title = computed(() => heroRom.value?.name ?? "");
const platformLabel = computed(
  () => container.value?.label ?? rom.value?.platform_slug?.toUpperCase() ?? "",
);

const backRoute = computed(() =>
  rom.value
    ? { name: ROUTES.ROM, params: { rom: rom.value.id } }
    : { name: ROUTES.HOME },
);

// Background art keeps the plain 2D cover while the launch screen is up;
// clear it once the player goes full-bleed so the stream isn't fought
// by a blurred backdrop behind the iframe.
const bgCoverUrl = computed(() => {
  if (!rom.value) return null;
  return (
    rom.value.path_cover_large ??
    rom.value.path_cover_small ??
    rom.value.url_cover ??
    null
  );
});

watch(
  bgCoverUrl,
  (url) => setBgArt(playerState.value === "playing" ? null : url),
  {
    immediate: true,
  },
);

watch(playerState, (state) =>
  setBgArt(state === "playing" ? null : bgCoverUrl.value),
);

// While a session is launching or playing the emulator owns the controller:
// this flag mutes useGamepad's pad->UI translation so button presses reach
// the stream instead of navigating (or closing) the RomM UI.
const sessionActive = computed(
  () => playerState.value === "playing" || playerState.value === "loading",
);
watch(sessionActive, (active) => playingStore.setPlaying(active));

// Sync volume slider (0-1) and mute button to the broker in real time.
// Debounced via watch — only fires after the value settles for 150ms.
let volumeDebounce: ReturnType<typeof setTimeout> | null = null;
watch(volume, (val) => {
  if (volumeDebounce) clearTimeout(volumeDebounce);
  volumeDebounce = setTimeout(() => {
    const platform = rom.value?.platform_slug;
    if (platform)
      streamingApi
        .setVolume(platform, Math.round(val * 100))
        .catch((err) => console.warn("[streaming] Could not set volume:", err));
  }, 150);
});

let uiTimeout: ReturnType<typeof setTimeout> | null = null;

// Cleanup refs for iframe listener management.
let attachTimeouts: ReturnType<typeof setTimeout>[] = [];
let iframeLoadCleanup: (() => void) | null = null;
let contentWindowCleanup: (() => void) | null = null;

onMounted(async () => {
  await fetchRom();
  document.addEventListener("fullscreenchange", onFullscreenChange);
  showUI();
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  if (uiTimeout) clearTimeout(uiTimeout);
  if (volumeDebounce) clearTimeout(volumeDebounce);
  attachTimeouts.forEach((id) => clearTimeout(id));
  attachTimeouts = [];
  iframeLoadCleanup?.();
  iframeLoadCleanup = null;
  contentWindowCleanup?.();
  contentWindowCleanup = null;
  // Every exit path (Stop, Save & Exit, back nav) unmounts the view, so this
  // is the single choke point for recording the session.
  playSession.flush();
  // Hand controller input back to the UI regardless of how we leave.
  playingStore.setPlaying(false);
  if (playerState.value === "exited") {
    // handleSaveAndExit already released the session, nothing to do.
    return;
  }
  if (playerState.value === "playing") {
    // Navigation away while a game is active. Fire save+kill in the
    // broker background and return immediately so navigation is never
    // held up.
    void streamingStore.saveAndExit(
      rom.value?.platform_slug ?? "",
      capabilities.value.autosaveSlot,
      false,
    );
  } else {
    // No active game (or handleSaveAndExit already ran) — plain release.
    void streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  }
});

async function fetchRom(): Promise<void> {
  try {
    const { data } = await romApi.getRom({ romId: romId.value });
    rom.value = data;
  } catch {
    playerState.value = "error";
    errorType.value = "server";
    errorMessage.value = t("play.stream-error-load-rom");
  }
}

function showUI(): void {
  isUIVisible.value = true;
  if (uiTimeout) clearTimeout(uiTimeout);
  uiTimeout = setTimeout(() => {
    isUIVisible.value = false;
  }, 1500);
}

/** Attach mousemove listener to iframe contentWindow if same-origin.
 * Cleans up any previous load listener before adding a new one. Guards
 * against double-attachment across repeated calls. */
function attachIframeListeners(): void {
  const frame = streamFrame.value;
  if (!frame) return;

  // Remove stale load listener from a prior call.
  iframeLoadCleanup?.();
  iframeLoadCleanup = null;

  const tryAttach = (): void => {
    if (contentWindowCleanup) return;
    try {
      if (frame.contentWindow) {
        frame.contentWindow.addEventListener("mousemove", showUI);
        frame.contentWindow.addEventListener("mousedown", showUI);
        frame.contentWindow.addEventListener("touchstart", showUI);
        contentWindowCleanup = () => {
          try {
            frame.contentWindow?.removeEventListener("mousemove", showUI);
            frame.contentWindow?.removeEventListener("mousedown", showUI);
            frame.contentWindow?.removeEventListener("touchstart", showUI);
          } catch {
            // Cross-origin — listeners were never added, nothing to remove.
          }
        };
      }
    } catch {
      // Cross-origin container, can't access contentWindow.
    }
  };

  frame.addEventListener("load", tryAttach);
  iframeLoadCleanup = () => frame.removeEventListener("load", tryAttach);
  tryAttach();
}

async function handlePlay(): Promise<void> {
  if (!rom.value) return;
  if (!container.value) {
    playerState.value = "error";
    errorType.value = "not_configured";
    errorMessage.value = t("play.stream-error-not-configured", {
      platform: rom.value.platform_slug,
    });
    return;
  }

  playerState.value = "loading";
  errorType.value = null;
  occupiedBy.value = null;

  try {
    // The backend derives the ROM's filesystem path and platform from the id.
    const session = await streamingStore.claimSession(rom.value.id);
    containerHost.value = session.host;
    playerState.value = "playing";

    // Wait for the DOM to update and the iframe to exist.
    attachTimeouts.forEach((id) => clearTimeout(id));
    attachTimeouts = [];
    attachTimeouts.push(setTimeout(attachIframeListeners, 100));
    // Some frames are slow to initialize their window — retry once more.
    attachTimeouts.push(setTimeout(attachIframeListeners, 500));
  } catch (err: unknown) {
    playerState.value = "error";

    const error = err as {
      status?: number;
      detail?: string | { rom_name: string; claimed_at: string } | null;
      message?: string;
    };

    if (error.status === 409) {
      errorType.value = "occupied";
      occupiedBy.value = typeof error.detail === "object" ? error.detail : null;
    } else if (error.status === 404) {
      // The backend raises 404 for two distinct cases: a missing streaming
      // container for the platform, and the ROM itself not being found
      // (e.g. deleted between fetchRom and the claim). Disambiguate by the
      // detail string so the message matches the real failure.
      const detail = typeof error.detail === "string" ? error.detail : "";
      if (detail.includes("ROM not found")) {
        errorType.value = "rom_not_found";
        errorMessage.value = t("play.stream-error-rom-not-found");
      } else {
        errorType.value = "not_configured";
        errorMessage.value = t("play.stream-error-not-configured", {
          platform: rom.value.platform_slug,
        });
      }
    } else {
      errorType.value = "server";
      errorMessage.value = error.message ?? t("play.stream-error-generic");
    }
  }

  // Start timing the session once the claim succeeds and playback is live.
  // The session is ingested on unmount, which updates last_played /
  // now_playing / status server-side.
  if (rom.value && playerState.value === "playing") {
    playSession.start(rom.value);
  }
}

async function handleStop(): Promise<void> {
  await streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  // "exited" tells onBeforeUnmount the session is already released, so
  // the navigation below doesn't trigger a second DELETE.
  playerState.value = "exited";
  containerHost.value = "";
  router.push(backRoute.value);
}

async function handleSaveAndExit(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isSavingAndExiting.value = true;
  let saved = false;
  try {
    saved = await streamingStore.saveAndExit(
      rom.value.platform_slug,
      capabilities.value.autosaveSlot,
      true,
    );
  } finally {
    isSavingAndExiting.value = false;
    playerState.value = "exited";
    containerHost.value = "";
  }
  if (!saved) {
    snackbar.warning(t("play.stream-save-unconfirmed"), { timeout: 6000 });
  }
  // Outside finally so we always navigate away, even if the save failed.
  router.push(backRoute.value);
}

async function handleSaveState(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isSavingState.value = true;
  try {
    await streamingApi.saveState(rom.value.platform_slug, selectedSlot.value);
  } catch (err) {
    console.warn("[streaming] Could not save state:", err);
  } finally {
    isSavingState.value = false;
  }
}

async function handleLoadState(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isLoadingState.value = true;
  try {
    await streamingApi.loadState(rom.value.platform_slug, selectedSlot.value);
  } catch (err) {
    console.warn("[streaming] Could not load state:", err);
  } finally {
    isLoadingState.value = false;
  }
}

async function handleLoadAutosave(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isLoadingAutosave.value = true;
  try {
    await streamingApi.loadState(
      rom.value.platform_slug,
      capabilities.value.autosaveSlot,
    );
  } catch (err) {
    console.warn("[streaming] Could not load state:", err);
  } finally {
    isLoadingAutosave.value = false;
  }
}

async function toggleFullscreen(): Promise<void> {
  if (!playerWrapper.value) return;
  try {
    if (!document.fullscreenElement) {
      await playerWrapper.value.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  } catch {
    // Fullscreen request denied (permissions policy or user-gesture requirement).
  }
}

function toggleMute(): void {
  isMuted.value = !isMuted.value;
  const platform = rom.value?.platform_slug;
  if (platform)
    streamingApi
      .setMute(platform, isMuted.value)
      .catch((err) => console.warn("[streaming] Could not set mute:", err));
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

const showLaunchScreen = computed(
  () =>
    playerState.value === "idle" ||
    playerState.value === "loading" ||
    playerState.value === "error",
);
</script>

<template>
  <section v-if="rom || heroSeed" class="r-v2-stream">
    <!-- Launch screen -->
    <div v-if="showLaunchScreen" class="r-v2-stream__launch">
      <aside class="r-v2-stream__cover">
        <GameCover
          class="r-v2-stream__cover-box"
          :rom="heroRom"
          :title="title"
          :identified="heroRom?.is_identified ?? true"
          :morph-id="`stream-cover-${romId}`"
          morph-static
          hover-motion
        />
        <h1 class="r-v2-stream__title">
          {{ title || t("play.stream-unknown-game") }}
        </h1>
        <p class="r-v2-stream__subtitle">
          {{ platformLabel }} · {{ t("play.stream-subtitle") }}
        </p>
      </aside>

      <div class="r-v2-stream__panel">
        <RAlert
          v-if="playerState === 'error' && errorType === 'occupied'"
          type="warning"
          variant="translucent"
          class="r-v2-stream__alert"
        >
          <template #title>{{ t("play.stream-occupied-title") }}</template>
          <span v-if="occupiedBy">
            {{
              t("play.stream-occupied-body", {
                rom: occupiedBy.rom_name,
                time: formatTime(occupiedBy.claimed_at),
              })
            }}
          </span>
          <span v-else>{{ t("play.stream-occupied-fallback") }}</span>
        </RAlert>

        <RAlert
          v-else-if="playerState === 'error'"
          type="error"
          variant="translucent"
          :text="errorMessage"
          class="r-v2-stream__alert"
        />

        <div class="r-v2-stream__actions">
          <RBtn
            size="large"
            variant="flat"
            color="primary"
            prepend-icon="mdi-play"
            :loading="playerState === 'loading'"
            :disabled="playerState === 'loading'"
            class="r-v2-stream__play"
            @click="handlePlay"
          >
            {{
              playerState === "error" && errorType === "occupied"
                ? t("play.stream-try-again")
                : t("play.play")
            }}
          </RBtn>

          <RBtn
            variant="text"
            size="large"
            prepend-icon="mdi-arrow-left"
            :to="backRoute"
          >
            {{ t("play.back-to-game-details") }}
          </RBtn>
        </div>
      </div>
    </div>

    <!-- Active player (shown after session is claimed) -->
    <div
      v-show="playerState === 'playing'"
      ref="playerWrapper"
      class="r-v2-stream__player"
      :class="{ 'r-v2-stream__player--hide-cursor': !isUIVisible }"
      role="presentation"
      @mousemove="showUI"
    >
      <!-- iframe points at the emulator container's built-in web UI. -->
      <iframe
        v-if="containerHost"
        ref="streamFrame"
        :src="containerHost"
        class="r-v2-stream__frame"
        allow="gamepad *; fullscreen *; autoplay *"
        allowfullscreen
        referrerpolicy="no-referrer"
        :title="t('play.stream-frame-title')"
      />

      <!-- Hover sensor for cross-origin fallback — bottom only so the
           top of the stream isn't blocked by an invisible trigger zone. -->
      <div class="r-v2-stream__sensor" @mousemove="showUI" />

      <!-- Control bar. -->
      <div
        class="r-v2-stream__bar"
        :class="{ 'r-v2-stream__bar--visible': isUIVisible }"
      >
        <span class="r-v2-stream__bar-title">{{ title }}</span>
        <span class="r-v2-stream__bar-subtitle">{{ platformLabel }}</span>

        <div class="r-v2-stream__spacer" />

        <!-- Volume controls -->
        <button
          type="button"
          class="r-v2-stream__icon-btn"
          :title="isMuted ? t('play.stream-unmute') : t('play.stream-mute')"
          :aria-label="
            isMuted ? t('play.stream-unmute') : t('play.stream-mute')
          "
          @click="toggleMute"
        >
          <RIcon :icon="isMuted ? 'mdi-volume-mute' : 'mdi-volume-high'" />
        </button>
        <input
          v-model.number="volume"
          type="range"
          min="0"
          max="1"
          step="0.01"
          class="r-v2-stream__volume"
          :title="t('play.stream-volume')"
          :aria-label="t('play.stream-volume')"
          :disabled="isMuted"
        />

        <!-- Save/load state controls (hidden for platforms with no save state support). -->
        <template v-if="capabilities.maxSlots > 0">
          <label class="r-v2-stream__slot">
            <span class="sr-only">{{ t("play.stream-save-slot") }}</span>
            <select
              v-model.number="selectedSlot"
              :title="t('play.stream-save-slot')"
            >
              <option v-for="n in capabilities.maxSlots" :key="n" :value="n">
                {{ t("play.stream-slot-n", { n }) }}
              </option>
            </select>
          </label>

          <button
            type="button"
            class="r-v2-stream__icon-btn"
            :title="t('play.stream-save-state')"
            :aria-label="t('play.stream-save-state')"
            :disabled="
              isSavingState ||
              isLoadingState ||
              isLoadingAutosave ||
              isSavingAndExiting
            "
            @click="handleSaveState"
          >
            <RSpinner v-if="isSavingState" :size="16" />
            <RIcon v-else icon="mdi-content-save-outline" />
          </button>

          <button
            type="button"
            class="r-v2-stream__icon-btn"
            :title="t('play.stream-load-state')"
            :aria-label="t('play.stream-load-state')"
            :disabled="
              isSavingState ||
              isLoadingState ||
              isLoadingAutosave ||
              isSavingAndExiting
            "
            @click="handleLoadState"
          >
            <RSpinner v-if="isLoadingState" :size="16" />
            <RIcon v-else icon="mdi-restore" />
          </button>

          <button
            v-if="capabilities.hasAutosave"
            type="button"
            class="r-v2-stream__icon-btn"
            :title="t('play.stream-load-autosave')"
            :aria-label="t('play.stream-load-autosave')"
            :disabled="
              isSavingState ||
              isLoadingState ||
              isLoadingAutosave ||
              isSavingAndExiting
            "
            @click="handleLoadAutosave"
          >
            <RSpinner v-if="isLoadingAutosave" :size="16" />
            <RIcon v-else icon="mdi-history" />
          </button>
        </template>

        <button
          type="button"
          class="r-v2-stream__icon-btn"
          :title="
            isFullscreen
              ? t('play.stream-exit-fullscreen')
              : t('play.stream-fullscreen')
          "
          :aria-label="
            isFullscreen
              ? t('play.stream-exit-fullscreen')
              : t('play.stream-fullscreen')
          "
          @click="toggleFullscreen"
        >
          <RIcon
            :icon="isFullscreen ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'"
          />
        </button>

        <button
          type="button"
          class="r-v2-stream__icon-btn"
          :title="t('play.stream-save-and-exit')"
          :aria-label="t('play.stream-save-and-exit')"
          :disabled="isSavingAndExiting"
          @click="handleSaveAndExit"
        >
          <RSpinner v-if="isSavingAndExiting" :size="16" />
          <RIcon v-else icon="mdi-exit-to-app" />
        </button>

        <button
          type="button"
          class="r-v2-stream__icon-btn r-v2-stream__icon-btn--danger"
          :title="t('play.stream-stop')"
          :aria-label="t('play.stream-stop')"
          :disabled="isSavingAndExiting"
          @click="handleStop"
        >
          <RIcon icon="mdi-stop" />
        </button>
      </div>
    </div>
  </section>

  <section v-else class="r-v2-stream__loading">
    <RSpinner :size="40" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-stream {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 24px var(--r-row-pad) 48px;
}

.r-v2-stream__launch {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 24px;
  max-width: 820px;
  margin: 0 auto;
}

.r-v2-stream__cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.r-v2-stream__cover-box {
  --r-cover-radius: var(--r-radius-lg);
}
.r-v2-stream__cover-box:not(.game-cover--alt) {
  box-shadow: 0 18px 36px color-mix(in srgb, black 55%, transparent);
}

.r-v2-stream__title {
  margin: 10px 0 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}

.r-v2-stream__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-stream__panel {
  display: flex;
  flex-direction: column;
  align-self: center;
  gap: 16px;
}

.r-v2-stream__alert {
  max-width: 440px;
}

.r-v2-stream__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.r-v2-stream__play {
  min-width: 140px;
}

/* Active player — full bleed below the nav. */
.r-v2-stream__player {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  display: flex;
  flex-direction: column;
  background: #0d0d0d;
  z-index: 1;
  overflow: hidden;
}
.r-v2-stream__player--hide-cursor {
  cursor: none;
}

.r-v2-stream__frame {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
  background: #000;
  display: block;
}

.r-v2-stream__sensor {
  position: absolute;
  left: 0;
  width: 100%;
  bottom: 0;
  height: 80px;
  z-index: 5;
  background: transparent;
}

.r-v2-stream__bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  min-height: 48px;
  background: rgba(18, 18, 18, 0.5);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  z-index: 10;
  box-shadow: 0 -4px 10px rgba(0, 0, 0, 0.3);

  /* visibility/opacity avoids layout flashes; GPU-promoted. */
  visibility: hidden;
  opacity: 0;
  transition:
    opacity 0.3s ease,
    visibility 0.3s ease;
  will-change: opacity;
  transform: translateZ(0);
}
.r-v2-stream__bar--visible {
  visibility: visible;
  opacity: 1;
}

.r-v2-stream__bar-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-medium);
  color: rgba(255, 255, 255, 0.92);
}
.r-v2-stream__bar-subtitle {
  font-size: var(--r-font-size-xs);
  color: rgba(255, 255, 255, 0.6);
  white-space: nowrap;
}

.r-v2-stream__spacer {
  flex: 1;
}

.r-v2-stream__icon-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-radius-sm);
  cursor: pointer;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}
.r-v2-stream__icon-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}
.r-v2-stream__icon-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.r-v2-stream__icon-btn--danger:hover:not(:disabled) {
  background: rgba(244, 67, 54, 0.2);
  color: #ff5a4d;
}

.r-v2-stream__volume {
  -webkit-appearance: none;
  appearance: none;
  width: 80px;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.2);
  outline: none;
  cursor: pointer;
  transition: background 0.2s ease;
}
.r-v2-stream__volume::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
}
.r-v2-stream__volume::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
}
.r-v2-stream__volume:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.r-v2-stream__slot select {
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--r-radius-sm);
  color: rgba(255, 255, 255, 0.87);
  cursor: pointer;
  font-size: 12px;
  height: 28px;
  outline: none;
  padding: 0 6px;
  width: 68px;
}
.r-v2-stream__slot select:hover {
  background: rgba(255, 255, 255, 0.15);
}
.r-v2-stream__slot select option {
  background: #1e1e1e;
  color: rgba(255, 255, 255, 0.87);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.r-v2-stream__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}

html[data-bp~="xs"] .r-v2-stream__launch {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-stream__cover {
  max-width: 240px;
  margin: 0 auto;
}
</style>
