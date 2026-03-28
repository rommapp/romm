<template>
  <v-main class="stream-player-main">
    <!-- Launch screen  -->
    <div
      v-if="
        playerState === 'idle' ||
        playerState === 'loading' ||
        playerState === 'error'
      "
      class="launch-screen"
    >
      <!-- Cover art -->
      <v-img
        v-if="rom?.cover_url"
        :src="rom.cover_url"
        class="launch-cover mx-auto mb-5"
        width="200"
        rounded="lg"
        cover
      />
      <v-icon v-else size="96" color="grey-darken-1" class="mb-5">
        mdi-disc
      </v-icon>

      <h1 class="text-h5 font-weight-bold text-center mb-1">
        {{ rom?.name ?? "Unknown Game" }}
      </h1>
      <p class="text-caption text-medium-emphasis text-center mb-6">
        {{ platformLabel }} · Streaming
      </p>

      <!-- Session-in-use alert -->
      <v-alert
        v-if="playerState === 'error' && errorType === 'occupied'"
        type="warning"
        variant="tonal"
        class="mb-5"
        max-width="440"
      >
        <strong>Session in use.</strong><br />
        <span v-if="occupiedBy">
          {{ occupiedBy.rom_name }} has been playing since
          {{ formatTime(occupiedBy.claimed_at) }}.
        </span>
        <span v-else>Someone else is currently playing. Try again later.</span>
      </v-alert>

      <!-- Generic error alert -->
      <v-alert
        v-else-if="playerState === 'error'"
        type="error"
        variant="tonal"
        class="mb-5"
        max-width="440"
      >
        {{ errorMessage }}
      </v-alert>

      <!-- Action buttons -->
      <div class="d-flex gap-3 justify-center flex-wrap">
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-play"
          :loading="playerState === 'loading'"
          :disabled="playerState === 'loading'"
          @click="handlePlay"
        >
          {{
            playerState === "error" && errorType === "occupied"
              ? "Try Again"
              : "Play"
          }}
        </v-btn>

        <v-btn
          variant="tonal"
          size="large"
          prepend-icon="mdi-arrow-left"
          :to="backRoute"
        >
          Back
        </v-btn>
      </div>
    </div>

    <!-- Active player (shown after session is claimed) -->
    <div
      v-show="playerState === 'playing'"
      ref="playerWrapper"
      class="player-wrapper"
    >
      <!-- Control bar — mirrors the EmulatorJS player bar style -->
      <div class="player-control-bar">
        <v-btn
          icon
          variant="text"
          density="compact"
          :to="backRoute"
          title="Back to game"
          @click.prevent="handleStop"
        >
          <v-icon>mdi-arrow-left</v-icon>
        </v-btn>

        <span class="player-title text-body-2 font-weight-medium ml-1">
          {{ rom?.name }}
        </span>

        <span class="text-caption text-medium-emphasis ml-2">
          · {{ platformLabel }}
        </span>

        <v-spacer />

        <v-btn
          icon
          variant="text"
          density="compact"
          :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
          @click="toggleFullscreen"
        >
          <v-icon>{{
            isFullscreen ? "mdi-fullscreen-exit" : "mdi-fullscreen"
          }}</v-icon>
        </v-btn>

        <v-btn
          icon
          variant="text"
          density="compact"
          color="error"
          title="Stop and release session"
          @click="handleStop"
        >
          <v-icon>mdi-stop</v-icon>
        </v-btn>
      </div>

      <!-- iframe points at the emulator container's built-in web UI -->
      <iframe
        v-if="containerHost"
        ref="streamFrame"
        :src="containerHost"
        class="stream-frame"
        allow="gamepad *; fullscreen *; autoplay *"
        allowfullscreen
        referrerpolicy="no-referrer"
        title="Game stream"
      />
    </div>
  </v-main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStreamingStore } from "@/stores/streaming";

interface Rom {
  id: number;
  name: string;
  file_name: string;
  full_path: string;
  platform_slug: string;
  cover_url?: string;
}

type PlayerState = "idle" | "loading" | "playing" | "error";
type ErrorType = "occupied" | "not_configured" | "server" | null;

const route = useRoute();
const router = useRouter();
const streamingStore = useStreamingStore();

const rom = ref<Rom | null>(null);
const playerState = ref<PlayerState>("idle");
const errorType = ref<ErrorType>(null);
const errorMessage = ref<string>("");
const occupiedBy = ref<{ rom_name: string; claimed_at: string } | null>(null);
const containerHost = ref<string>("");
const isFullscreen = ref(false);

const playerWrapper = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);

const romId = computed(() => Number(route.params.rom));

const container = computed(() =>
  rom.value
    ? streamingStore.containerForPlatform(rom.value.platform_slug)
    : null,
);

const platformLabel = computed(
  () => container.value?.label ?? rom.value?.platform_slug?.toUpperCase() ?? "",
);

const backRoute = computed(() =>
  rom.value ? { name: "rom", params: { rom: rom.value.id } } : { name: "home" },
);

onMounted(async () => {
  await fetchRom();
  document.addEventListener("fullscreenchange", onFullscreenChange);
});

onBeforeUnmount(async () => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  // Always release the session when the component is torn down,
  // whether the user clicked Stop or just navigated away.
  if (playerState.value === "playing") {
    await streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  }
});

async function fetchRom(): Promise<void> {
  try {
    const res = await fetch(`/api/roms/${romId.value}`);
    if (!res.ok) throw new Error("ROM not found");
    rom.value = await res.json();
  } catch {
    playerState.value = "error";
    errorType.value = "server";
    errorMessage.value = "Could not load ROM details.";
  }
}

async function handlePlay(): Promise<void> {
  if (!rom.value) return;
  if (!container.value) {
    playerState.value = "error";
    errorType.value = "not_configured";
    errorMessage.value = `No streaming container is configured for ${rom.value?.platform_slug}.`;
    return;
  }

  playerState.value = "loading";
  errorType.value = null;
  occupiedBy.value = null;

  // Build the full ROM path as it appears inside the RomM container.
  // RomM mounts the library at /romm/library/roms, so the full path is:
  //   /romm/library/roms/<platform_slug>/<file_name>
  // This must match what the pcsx2 container can see at the same path.
  const romPath = `/romm/library/${rom.value.full_path}`;

  try {
    const session = await streamingStore.claimSession(
      rom.value.platform_slug,
      romPath,
      rom.value.name,
    );
    containerHost.value = session.host;
    playerState.value = "playing";
  } catch (err: any) {
    playerState.value = "error";

    if (err.status === 409) {
      errorType.value = "occupied";
      occupiedBy.value = err.detail ?? null;
    } else if (err.status === 404) {
      errorType.value = "not_configured";
      errorMessage.value =
        "No streaming container configured for this platform.";
    } else {
      errorType.value = "server";
      errorMessage.value = err.message ?? "An unexpected error occurred.";
    }
  }
}

async function handleStop(): Promise<void> {
  await streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  playerState.value = "idle";
  containerHost.value = "";
  router.push(backRoute.value);
}

async function toggleFullscreen(): Promise<void> {
  if (!playerWrapper.value) return;
  if (!document.fullscreenElement) {
    await playerWrapper.value.requestFullscreen();
  } else {
    await document.exitFullscreen();
  }
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
</script>

<style scoped>
/* Remove default v-main padding so the player fills the viewport */
.stream-player-main {
  padding: 0 !important;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0d0d0d;
}

.launch-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 2rem 1rem;
}

.launch-cover {
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
}

.player-wrapper {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
}

.player-control-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  min-height: 44px;
  flex-shrink: 0;
  background: rgba(18, 18, 18, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.player-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.stream-frame {
  flex: 1;
  width: 100%;
  border: none;
  background: #000;
  display: block;
}

:fullscreen .player-control-bar {
  display: none;
}

:fullscreen .stream-frame {
  height: 100vh;
}
</style>
