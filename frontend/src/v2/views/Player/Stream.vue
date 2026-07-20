<script setup lang="ts">
// Stream: v2 player for containerized emulator streaming. A native
// emulator runs in a separate container with a Selkies WebRTC stream;
// RomM claims a session through the `/api/streaming` endpoints and
// shows the stream in an iframe pointed at the container's web UI.
//
// Layout mirrors the EmulatorJS view, three columns pre-game:
//   1. Hero: cover + title + "Play on <emulator>" CTA + back links.
//   2. Session: where the game runs, save-slot capabilities, and any
//      claim errors (occupied / not configured / server).
//   3. Setup: default save slot + fullscreen-on-play.
//
// The running state is a fixed stage hosting the Selkies iframe with an
// auto-hiding control bar (volume, save/load state, fullscreen, exit).
import {
  RAlert,
  RBtn,
  RCard,
  RDialog,
  RIcon,
  RSelect,
  RSlider,
  RSwitch,
} from "@v2/lib";
import { isAxiosError } from "axios";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import type { UserStateSchema } from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import streamingApi from "@/services/api/streaming";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import {
  type SessionStatus,
  type SessionTermination,
  useStreamingStore,
} from "@/stores/streaming";
import AssetPreview from "@/v2/components/Player/AssetPreview.vue";
import MemoryCardPicker from "@/v2/components/Player/MemoryCardPicker.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useCoverArt } from "@/v2/composables/useCoverArt";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useInputModality } from "@/v2/composables/useInputModality";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

type PlayerState = "idle" | "loading" | "playing" | "error" | "exited";
type ErrorType =
  "occupied" | "not_configured" | "rom_not_found" | "server" | null;

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = storeAuth();
const playingStore = storePlaying();
const streamingStore = useStreamingStore();
const snackbar = useSnackbar();
const { fullscreenOnPlay } = useFullscreenPref();
const { modality } = useInputModality();

const rom = ref<DetailedRom | null>(null);
const playerState = ref<PlayerState>("idle");
const errorType = ref<ErrorType>(null);
const errorMessage = ref<string>("");
const errorHint = ref<string>("");
const occupiedBy = ref<{ rom_name: string; claimed_at: string } | null>(null);
const containerHost = ref<string>("");
const isFullscreen = ref(false);
const isUIVisible = ref(true);
const isSavingAndExiting = ref(false);
const isSavingState = ref(false);
const isLoadingState = ref(false);
const isLoadingAutosave = ref(false);
const selectedSlot = ref(1);
const volume = ref(100);
const isMuted = ref(false);

const gameRunning = computed(() => playerState.value === "playing");

// While a session is active (launching or playing) the emulator owns the
// controller: the global playing flag mutes useGamepad's UI translation,
// which would otherwise treat B as history-back (ending the session) and
// Start as the user menu. The exit dialog is the sanctioned way out.
const sessionActive = computed(
  () => playerState.value === "playing" || playerState.value === "loading",
);
watch(sessionActive, (active) => {
  playingStore.setPlaying(active);
  if (active) startSessionPoll();
  else stopSessionPoll();
});

// Rom id straight from the route param (available before `rom` resolves),
// so the hero cover paints its `view-transition-name` immediately and the
// shared-element morph from the gallery / details cover pairs on entry.
const morphRomId = computed(() => {
  const r = route.params.rom;
  return typeof r === "string" ? r : null;
});

// Seed synchronously so the hero cover is already in the DOM when the view
// transition captures this view (same pattern as the EmulatorJS view).
const seededRom = storeRoms().currentRom;
if (seededRom && String(seededRom.id) === morphRomId.value) {
  rom.value = seededRom;
}
const heroSeed = ref<SimpleRom | null>(null);
if (!rom.value && morphRomId.value != null) {
  heroSeed.value = storeGalleryRoms().getRomById(Number(morphRomId.value));
}
const heroRom = computed<DetailedRom | SimpleRom | null>(
  () => rom.value ?? heroSeed.value,
);

const setBgArt = useBackgroundArt();

// Alt-art detection only drives the purple glow: a floating disc /
// cartridge reads better without a frame (same rule as EmulatorJS).
const art = useCoverArt(() => heroRom.value);
const heroIsAlt = computed(
  () =>
    art.style.value !== "cover_path" &&
    !!(art.coverUrl.value ?? art.fallbackUrl.value),
);
const coverRef = ref<InstanceType<typeof GameCover> | null>(null);

const bgCoverUrl = computed(() => {
  const r = rom.value;
  if (!r) return null;
  return r.path_cover_large ?? r.path_cover_small ?? r.url_cover ?? null;
});

// Background art keeps the plain 2D cover while the launch screen is up;
// clear it once the player goes full-bleed so the stream isn't fought
// by a blurred backdrop behind the iframe.
watch(
  bgCoverUrl,
  (url) => setBgArt(playerState.value === "playing" ? null : url),
  { immediate: true },
);

watch(playerState, (state) =>
  setBgArt(state === "playing" ? null : bgCoverUrl.value),
);

const container = computed(() =>
  rom.value
    ? streamingStore.containerForPlatform(rom.value.platform_slug)
    : null,
);

const capabilities = computed(() =>
  streamingStore.platformCapabilities(rom.value?.platform_slug),
);

// ── Resume-from-state picker ────────────────────────────────────────
// States the container's emulator can resume from: the user's own plus
// other users' public ones (that is what all_user_states carries), kept
// to this emulator's namespace so EmulatorJS states stay out. The list
// arrives newest-first from the backend.
const selectedState = ref<UserStateSchema | null>(null);

const streamStates = computed<UserStateSchema[]>(() => {
  const emulator = container.value?.emulator?.toLowerCase();
  if (!rom.value || !emulator) return [];
  return (rom.value.all_user_states ?? []).filter(
    (s) => (s.emulator ?? "").toLowerCase() === emulator,
  );
});

// Preselect the newest state so Play resumes where the user left off;
// clearing the preview (start fresh) is one click away.
watch(
  streamStates,
  (states) => {
    const current = selectedState.value;
    if (current && !states.some((s) => s.id === current.id)) {
      selectedState.value = null;
    }
    if (!selectedState.value && states.length > 0) {
      selectedState.value = states[0];
    }
  },
  { immediate: true },
);

function pickState(state: UserStateSchema): void {
  selectedState.value = state;
}

// ── Memory card picker (whole-card sync) ────────────────────────────
// Which card to hydrate onto the container at claim. Only shown for
// containers that sync whole cards (PCSX2). Null means "let the backend
// pick the newest / auto-create a blank one". MemoryCardPicker owns the
// fetch + default-newest selection; we just carry the id to claim.
const selectedMemoryCardId = ref<number | null>(null);

// Clamp so a platform switch to fewer slots never sends an
// out-of-range slot to the broker.
watch(
  () => capabilities.value.maxSlots,
  (max) => {
    if (selectedSlot.value > max) selectedSlot.value = 1;
  },
);

const slotItems = computed(() =>
  Array.from({ length: capabilities.value.maxSlots }, (_, i) => ({
    title: t("play.stream-slot-n", { n: i + 1 }),
    value: i + 1,
  })),
);

const title = computed(
  () => heroRom.value?.name || heroRom.value?.fs_name_no_ext || "",
);

const platformLabel = computed(
  () =>
    heroRom.value?.platform_custom_name ||
    heroRom.value?.platform_display_name ||
    rom.value?.platform_slug?.toUpperCase() ||
    "",
);

const emulatorLabel = computed(
  () => container.value?.label ?? platformLabel.value,
);

function focusPlayButton() {
  const btn = document.querySelector<HTMLElement>(".r-v2-stream__play");
  btn?.focus({ preventScroll: true });
}

// ── Live activity ("now playing") ──────────────────────────────────
const ACTIVITY_HEARTBEAT_MS = 30_000;
let activityHeartbeatTimer: ReturnType<typeof setInterval> | null = null;

function activityDeviceId(): string {
  return auth.user?.current_device_id ?? "web";
}

function emitActivityStart() {
  if (!auth.user || !rom.value) return;
  if (!socket.connected) socket.connect();
  socket.emit("activity:start", {
    rom_id: rom.value.id,
    device_id: activityDeviceId(),
  });
}

async function emitActivityHeartbeat() {
  if (!auth.user || !rom.value) return;
  socket.emit("activity:heartbeat", {
    rom_id: rom.value.id,
    device_id: activityDeviceId(),
  });
  // Also refresh the backend claim's liveness stamp: a session whose
  // heartbeat stops long enough counts as abandoned and can be taken over.
  // The same reply reports whether the claim is still ours, which is how an
  // admin force-release reaches this tab.
  if (sessionActive.value) {
    await handleSessionStatus(
      await streamingStore.heartbeatSession(rom.value.platform_slug),
    );
  }
}

// ── Force-release handling ─────────────────────────────────────────
// An admin can end this session from the activity panel. Nothing about the
// stream itself changes when that happens (the picture just stops), so the
// poll reply is what drives the player out, naming who ended it and why.
// The notice is a dialog rather than a snackbar: the player has just lost a
// running game and must acknowledge that before being sent back.
const endedDialogOpen = ref(false);
const endedNotice = ref<SessionTermination | null>(null);

// Headline: who ended it, said plainly enough that the player knows this was
// an admin action and not a crash. The reason, when one was given, is a
// separate line in the dialog rather than part of this sentence.
const endedMessage = computed(() => {
  const endedBy = endedNotice.value?.ended_by;
  if (endedBy) return t("play.session-ended-by", { user: endedBy });
  // No notice recorded: the claim expired or was released elsewhere.
  return t("play.session-ended");
});

const endedReason = computed(() => endedNotice.value?.reason ?? "");

async function handleSessionStatus(
  status: SessionStatus | null,
): Promise<void> {
  // Null means the poll failed, not that the session is gone. A transient
  // network error must never tear down a live game.
  if (!status || status.status !== "ended") return;
  // Already leaving under our own power (stop, save-and-exit, unload).
  if (!sessionActive.value) return;
  // The socket push arrives per-user, not per-platform (one room for every
  // stream the account touches), so a stale event for a different platform
  // must not tear down the one actually on screen.
  if (rom.value && status.platform !== rom.value.platform_slug) return;

  // Leave fullscreen before anything else. RDialog teleports to <body>,
  // outside the stage, so the notice would otherwise be painted under a
  // fullscreened stage; and tearing the stage down first would unmount the
  // fullscreen element out from under the in-flight exit request, leaving the
  // browser fullscreen over a dead stream.
  await leaveFullscreen();

  // "exited" both stops the route guard prompting and suppresses the unmount
  // release path, since the claim is already gone server-side.
  playerState.value = "exited";
  containerHost.value = "";
  stopActivityHeartbeat();

  endedNotice.value = status.termination ?? null;
  endedDialogOpen.value = true;
}

function dismissEndedDialog(): void {
  endedDialogOpen.value = false;
  backToRom();
}

// The socket push below is what actually drives an admin release out in
// close to real time. This poll is the fallback for a dropped/missed push
// (socket reconnecting, event lost) and for a background tab's throttled
// timers, so it runs far less often than the push needs to react.
const SESSION_POLL_MS = 30_000;

// Pushed by the backend the instant an admin force-releases this user's
// session (`_record_termination` in streaming.py), to the caller's own
// `user:{id}` room. Near-instant, unlike the poll above.
useSocketEvent<SessionTermination>("streaming:session-ended", (notice) => {
  void handleSessionStatus({
    status: "ended",
    platform: notice.platform ?? "",
    termination: notice,
  });
});
let sessionPollTimer: ReturnType<typeof setInterval> | null = null;
let sessionPollInFlight = false;

async function pollSessionStatus(): Promise<void> {
  // Skip rather than queue: a slow reply must not stack up requests.
  if (sessionPollInFlight || !sessionActive.value || !rom.value) return;
  sessionPollInFlight = true;
  try {
    await handleSessionStatus(
      await streamingStore.fetchSessionStatus(rom.value.platform_slug),
    );
  } finally {
    sessionPollInFlight = false;
  }
}

function startSessionPoll() {
  if (sessionPollTimer) return;
  sessionPollTimer = setInterval(pollSessionStatus, SESSION_POLL_MS);
}

function stopSessionPoll() {
  if (sessionPollTimer) {
    clearInterval(sessionPollTimer);
    sessionPollTimer = null;
  }
}

// A background tab's timers are throttled, so the poll may not have run for
// minutes. Re-check on the way back rather than leaving a dead stream on
// screen.
async function onVisibilityChange(): Promise<void> {
  if (document.hidden) return;
  await pollSessionStatus();
}

function emitActivityStop() {
  if (!auth.user) return;
  socket.emit("activity:stop", {
    device_id: activityDeviceId(),
  });
}

function startActivityHeartbeat() {
  if (activityHeartbeatTimer) return;
  activityHeartbeatTimer = setInterval(
    emitActivityHeartbeat,
    ACTIVITY_HEARTBEAT_MS,
  );
}

function stopActivityHeartbeat() {
  if (activityHeartbeatTimer) {
    clearInterval(activityHeartbeatTimer);
    activityHeartbeatTimer = null;
  }
}

watch(gameRunning, (running, prev) => {
  if (running && !prev) {
    emitActivityStart();
    startActivityHeartbeat();
    nextTick(focusStream);
  }
  if (prev && !running) {
    stopActivityHeartbeat();
    emitActivityStop();
    nextTick(focusPlayButton);
  }
});

// ── Volume / mute ───────────────────────────────────────────────────
// Debounced so the broker only hears the value once it settles.
let volumeDebounce: ReturnType<typeof setTimeout> | null = null;
watch(volume, (val) => {
  if (volumeDebounce) clearTimeout(volumeDebounce);
  volumeDebounce = setTimeout(() => {
    const platform = rom.value?.platform_slug;
    if (platform)
      streamingApi
        .setVolume(platform, Math.round(val))
        .catch((err) => console.warn("[streaming] Could not set volume:", err));
  }, 150);
});

function toggleMute(): void {
  isMuted.value = !isMuted.value;
  const platform = rom.value?.platform_slug;
  if (platform)
    streamingApi
      .setMute(platform, isMuted.value)
      .catch((err) => console.warn("[streaming] Could not set mute:", err));
}

// ── Auto-hiding control bar ────────────────────────────────────────
let uiTimeout: ReturnType<typeof setTimeout> | null = null;
const stageRef = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);

let attachTimeouts: ReturnType<typeof setTimeout>[] = [];
let iframeLoadCleanup: (() => void) | null = null;
let contentWindowCleanup: (() => void) | null = null;

function showUI(): void {
  isUIVisible.value = true;
  if (uiTimeout) clearTimeout(uiTimeout);
  uiTimeout = setTimeout(() => {
    isUIVisible.value = false;
    focusStream();
  }, 2500);
}

// Browsers only deliver gamepad input to the focused frame, so the Selkies
// iframe must hold focus for the emulator to see the controller. Called on
// game start, iframe load, and whenever the control bar hides (returning
// focus taken by a toolbar click).
function focusStream(): void {
  if (!gameRunning.value) return;
  streamFrame.value?.focus();
}

function handleMouseMove(): void {
  showUI();
}

// Attach pointer listeners inside the iframe when same-origin, so the
// control bar reappears while the pointer is over the stream. Cross-
// origin containers fall back to the bottom hover sensor.
function attachIframeListeners(): void {
  const frame = streamFrame.value;
  if (!frame) return;

  iframeLoadCleanup?.();
  iframeLoadCleanup = null;

  const tryAttach = (): void => {
    focusStream();
    if (contentWindowCleanup) return;
    try {
      if (frame.contentWindow) {
        frame.contentWindow.addEventListener("mousemove", handleMouseMove);
        frame.contentWindow.addEventListener("mousedown", handleMouseMove);
        frame.contentWindow.addEventListener("touchstart", handleMouseMove);
        contentWindowCleanup = () => {
          try {
            frame.contentWindow?.removeEventListener(
              "mousemove",
              handleMouseMove,
            );
            frame.contentWindow?.removeEventListener(
              "mousedown",
              handleMouseMove,
            );
            frame.contentWindow?.removeEventListener(
              "touchstart",
              handleMouseMove,
            );
          } catch {
            // Cross-origin: listeners were never added, nothing to remove.
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

// ── Session lifecycle ──────────────────────────────────────────────

// Plain-language "what could be wrong" hint for the claim error alert.
// Statuses mirror the backend contract: 502 broker rejected the launch,
// 503 broker unreachable, 401/403 auth, no status = RomM unreachable.
function hintForStatus(status?: number): string {
  const label = emulatorLabel.value;
  if (status === 503) return t("play.error-hint-unreachable", { label });
  if (status === 502) return t("play.error-hint-broker", { label });
  if (status === 401 || status === 403) return t("play.error-hint-auth");
  if (status === undefined) return t("play.error-hint-network");
  return t("play.error-hint-server");
}

async function onPlay(): Promise<void> {
  if (!rom.value) return;
  if (!container.value) {
    playerState.value = "error";
    errorType.value = "not_configured";
    errorMessage.value = t("play.stream-error-not-configured", {
      platform: rom.value.platform_slug,
    });
    errorHint.value = t("play.error-hint-not-configured");
    return;
  }

  playerState.value = "loading";
  errorType.value = null;
  errorHint.value = "";
  occupiedBy.value = null;

  // Launch flourish on the cover (disc drop / cartridge slot-in) while
  // the session claim is in flight.
  const insertMs = coverRef.value?.playLoad() ?? 0;
  const flourish =
    insertMs > 0
      ? new Promise((resolve) => setTimeout(resolve, insertMs))
      : Promise.resolve();

  if (auth.scopes.includes("roms.user.write")) {
    // Best-effort metadata update; a failure must not surface as an
    // unhandled rejection or block the launch.
    romApi
      .updateUserRomProps({
        romId: rom.value.id,
        data: rom.value.rom_user,
        updateLastPlayed: true,
      })
      .catch((err) => {
        console.warn("[stream] Could not update last-played:", err);
      });
  }

  try {
    // The backend derives the ROM's filesystem path and platform from the id.
    // A selected state rides along: its file is pushed to the broker and the
    // emulator loads it once the game is up.
    const session = await streamingStore.claimSession(
      rom.value.id,
      selectedState.value?.id,
      container.value?.supports_memory_cards
        ? (selectedMemoryCardId.value ?? undefined)
        : undefined,
    );
    if (session.resume === false) {
      snackbar.warning(t("play.resume-failed"));
    }
    await flourish;
    // Widen past TS's "loading" narrowing: the exit dialog can flip the
    // state to "exited" while the claim is awaited.
    const stateAfterClaim = playerState.value as PlayerState;
    if (stateAfterClaim === "exited") {
      // The launch was cancelled from the exit dialog while the claim was
      // in flight; the claim that just resolved re-acquired the session,
      // so release it again instead of entering the playing state.
      void streamingStore.releaseSession(rom.value.platform_slug);
      return;
    }
    containerHost.value = session.host;
    playerState.value = "playing";
    showUI();

    attachTimeouts.forEach((id) => clearTimeout(id));
    attachTimeouts = [];
    attachTimeouts.push(setTimeout(attachIframeListeners, 100));
    // Some frames are slow to initialize their window; try again later.
    attachTimeouts.push(setTimeout(attachIframeListeners, 500));

    if (fullscreenOnPlay.value) {
      await nextTick();
      try {
        await stageRef.value?.requestFullscreen();
      } catch {
        // Fullscreen denied (permissions policy / gesture requirement).
      }
    }
  } catch (err: unknown) {
    playerState.value = "error";

    // The store propagates the raw axios error; the status and the
    // backend's detail payload live on its response.
    const status = isAxiosError(err) ? err.response?.status : undefined;
    const detail: unknown = isAxiosError(err)
      ? err.response?.data?.detail
      : undefined;

    if (status === 409) {
      errorType.value = "occupied";
      occupiedBy.value =
        detail && typeof detail === "object"
          ? (detail as { rom_name: string; claimed_at: string })
          : null;
    } else if (status === 404) {
      // 404 covers two cases: no container configured for the platform,
      // and the ROM itself missing (deleted between fetch and claim).
      // The detail string disambiguates.
      if (typeof detail === "string" && detail.includes("ROM not found")) {
        errorType.value = "rom_not_found";
        errorMessage.value = t("play.stream-error-rom-not-found");
        errorHint.value = "";
      } else {
        errorType.value = "not_configured";
        errorMessage.value = t("play.stream-error-not-configured", {
          platform: rom.value?.platform_slug ?? "",
        });
        errorHint.value = t("play.error-hint-not-configured");
      }
    } else {
      errorType.value = "server";
      // Without a status the request never got a response, so the axios
      // message is meaningless - show a generic title and let the hint
      // explain the likely cause.
      errorMessage.value =
        (status !== undefined && err instanceof Error ? err.message : null) ??
        t("play.stream-error-generic");
      errorHint.value = hintForStatus(status);
    }
  }
}

async function performStop(): Promise<void> {
  await streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  // "exited" tells onBeforeUnmount the session is already released, so
  // navigating away afterwards doesn't trigger a second DELETE.
  playerState.value = "exited";
  containerHost.value = "";
}

async function handleStop(): Promise<void> {
  await performStop();
  backToRom();
}

async function performSaveAndExit(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  isSavingAndExiting.value = true;
  let saved = false;
  try {
    const result = await streamingStore.saveAndExit(
      rom.value.platform_slug,
      capabilities.value.autosaveSlot,
      true,
    );
    saved = result.saved;
    if (!result.released) {
      // The save-and-exit request failed, so the claim may still be held;
      // fall back to a plain release so the container is freed before the
      // player is marked exited.
      await streamingStore.releaseSession(rom.value.platform_slug);
    }
  } finally {
    isSavingAndExiting.value = false;
    playerState.value = "exited";
    containerHost.value = "";
  }
  if (!saved) {
    snackbar.warning(t("play.stream-save-unconfirmed"), {
      timeout: 6000,
      icon: "mdi-alert",
    });
  }
}

async function handleSaveAndExit(): Promise<void> {
  await performSaveAndExit();
  backToRom();
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

const stateActionBusy = computed(
  () =>
    isSavingState.value ||
    isLoadingState.value ||
    isLoadingAutosave.value ||
    isSavingAndExiting.value,
);

// ── Fullscreen ─────────────────────────────────────────────────────
async function toggleFullscreen(): Promise<void> {
  if (!stageRef.value) return;
  try {
    if (!document.fullscreenElement) {
      await stageRef.value.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  } catch {
    // Fullscreen denied (permissions policy / gesture requirement).
  }
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement;
}

// Drop out of fullscreen before showing anything teleported to <body>: a
// fullscreened element paints over the whole page, dialogs included.
async function leaveFullscreen(): Promise<void> {
  if (!document.fullscreenElement) return;
  try {
    await document.exitFullscreen();
  } catch (error) {
    // Worst case the dialog opens behind fullscreen, so this is not fatal, but
    // it is invisible from the UI and worth surfacing to anyone debugging it.
    console.warn("Failed to exit fullscreen", error);
  }
}

// ── Navigation ─────────────────────────────────────────────────────
function backToRom() {
  router.push({ name: ROUTES.ROM, params: { rom: rom.value?.id } });
}
function backToPlatform() {
  router.push({
    name: ROUTES.PLATFORM,
    params: { platform: rom.value?.platform_id },
  });
}

// ── Exit guard (big-picture safety) ────────────────────────────────
// While a session is active every way out funnels through one dialog:
// route-leave (B press, browser back, any link) is intercepted, and
// holding Select+Start on the pad opens it directly. A single stray
// button press can no longer kill the game.
const exitDialogOpen = ref(false);
const isStopping = ref(false);
// Set by the route-leave guard so a confirmed exit resumes the original
// navigation instead of forcing the ROM details page.
let pendingLeave: (() => void) | null = null;

async function openExitDialog(): Promise<void> {
  if (exitDialogOpen.value) return;
  await leaveFullscreen();
  exitDialogOpen.value = true;
}

watch(exitDialogOpen, (open) => {
  if (!open) {
    pendingLeave = null;
    if (gameRunning.value) nextTick(focusStream);
  }
});

onBeforeRouteLeave((to) => {
  if (!sessionActive.value) return true;
  pendingLeave = () => router.push(to.fullPath);
  void openExitDialog();
  return false;
});

function exitKeepPlaying(): void {
  exitDialogOpen.value = false;
}

// Both actions resolve before the dialog closes so their buttons can
// show a busy spinner (save-and-exit blocks on the broker's save+kill).
async function exitSaveAndQuit(): Promise<void> {
  const leave = pendingLeave;
  await performSaveAndExit();
  exitDialogOpen.value = false;
  (leave ?? backToRom)();
}

async function exitWithoutSaving(): Promise<void> {
  const leave = pendingLeave;
  isStopping.value = true;
  try {
    await performStop();
  } finally {
    isStopping.value = false;
  }
  exitDialogOpen.value = false;
  (leave ?? backToRom)();
}

// Dialogs have no automatic spatial navigation, so cycle focus between
// the action buttons on arrow keys (the d-pad arrives as synthetic
// ArrowLeft/ArrowRight keydowns from useGamepad).
function onExitDialogKeydown(event: KeyboardEvent): void {
  const arrows = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
  if (!arrows.includes(event.key)) return;
  const root = event.currentTarget as HTMLElement;
  const buttons = Array.from(
    root.querySelectorAll<HTMLElement>("button:not([disabled])"),
  );
  if (buttons.length === 0) return;
  const idx = buttons.indexOf(document.activeElement as HTMLElement);
  const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
  buttons[(idx + step + buttons.length) % buttons.length]?.focus();
  event.preventDefault();
}

// ── Select+Start exit chord ────────────────────────────────────────
// useGamepad is muted for the whole session (launch included), so the
// chord is read straight from the Gamepad API here; polling while
// "loading" keeps the cancel dialog reachable by pad if a launch hangs.
// The 1.5s hold filters out anything a game itself binds to Select+Start.
// Only standard-mapped pads participate: elsewhere indices 8/9 are not
// guaranteed to be Select+Start.
const EXIT_CHORD_HOLD_MS = 1500;
let chordRaf = 0;
let chordHeldSince = 0;

function pollExitChord(now: number): void {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  const held = Array.from(pads).some(
    (pad) =>
      pad &&
      pad.mapping === "standard" &&
      pad.buttons[8]?.pressed &&
      pad.buttons[9]?.pressed,
  );
  if (!held) {
    chordHeldSince = 0;
  } else if (!chordHeldSince) {
    chordHeldSince = now;
  } else if (now - chordHeldSince >= EXIT_CHORD_HOLD_MS) {
    chordHeldSince = 0;
    if (!exitDialogOpen.value) void openExitDialog();
  }
  chordRaf = requestAnimationFrame(pollExitChord);
}

watch(sessionActive, (active) => {
  if (active && !chordRaf) {
    chordRaf = requestAnimationFrame(pollExitChord);
  } else if (!active && chordRaf) {
    cancelAnimationFrame(chordRaf);
    chordRaf = 0;
    chordHeldSince = 0;
  }
});

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

// ── Unload teardown ─────────────────────────────────────────────────
// Vue teardown never runs when the tab closes or the browser quits, so
// pagehide is the only signal. The keepalive requests outlive the page;
// the broker-side save+kill then runs to completion server-side.
function onPageHide(): void {
  if (playerState.value === "exited") return;
  const platform = rom.value?.platform_slug ?? "";
  if (playerState.value === "playing") {
    streamingStore.saveAndExitKeepalive(
      platform,
      capabilities.value.autosaveSlot,
    );
  } else if (sessionActive.value) {
    streamingStore.releaseSessionKeepalive(platform);
  } else {
    return;
  }
  // Guards the in-app unmount path from double-releasing if the page
  // comes back from the bfcache and is then navigated normally.
  playerState.value = "exited";
}

onMounted(async () => {
  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("pagehide", onPageHide);

  try {
    const { data } = await romApi.getRom({
      romId: parseInt(route.params.rom as string),
    });
    rom.value = data;
  } catch {
    playerState.value = "error";
    errorType.value = "server";
    errorMessage.value = t("play.stream-error-load-rom");
    return;
  }

  if (rom.value) {
    document.title = `${rom.value.name} | Play`;
  }

  // Autofocus the Play CTA so gamepad/keyboard users land on the
  // primary action without an extra Tab.
  if (modality.value === "pad" || modality.value === "key") {
    await nextTick();
    focusPlayButton();
  }
});

onBeforeUnmount(() => {
  playingStore.setPlaying(false);
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  document.removeEventListener("visibilitychange", onVisibilityChange);
  window.removeEventListener("pagehide", onPageHide);
  if (uiTimeout) clearTimeout(uiTimeout);
  if (volumeDebounce) clearTimeout(volumeDebounce);
  attachTimeouts.forEach((id) => clearTimeout(id));
  attachTimeouts = [];
  if (chordRaf) {
    cancelAnimationFrame(chordRaf);
    chordRaf = 0;
  }
  iframeLoadCleanup?.();
  iframeLoadCleanup = null;
  contentWindowCleanup?.();
  contentWindowCleanup = null;
  stopActivityHeartbeat();
  stopSessionPoll();
  emitActivityStop();
  if (playerState.value === "exited") {
    // handleSaveAndExit / handleStop already released the session.
    return;
  }
  if (playerState.value === "playing") {
    // Navigation away while a game is active: fire save+kill in the
    // broker background so navigation is never held up.
    void streamingStore.saveAndExit(
      rom.value?.platform_slug ?? "",
      capabilities.value.autosaveSlot,
      false,
    );
  } else {
    void streamingStore.releaseSession(rom.value?.platform_slug ?? "");
  }
});
</script>

<template>
  <section v-if="rom || heroSeed" class="r-v2-stream">
    <!-- Pre-game configuration -->
    <div
      v-if="!gameRunning"
      class="r-v2-stream__config"
      :class="{ 'r-v2-stream__config--resume': streamStates.length > 0 }"
    >
      <!-- Hero: cover + title + Play CTA -->
      <RCard class="r-v2-stream__panel r-v2-stream__hero" variant="flat">
        <div
          class="r-v2-stream__cover"
          :class="{ 'r-v2-stream__cover--alt-art': heroIsAlt }"
        >
          <GameCover
            ref="coverRef"
            class="r-v2-stream__cover-box"
            :rom="heroRom"
            :title="title"
            :identified="heroRom?.is_identified ?? true"
            :morph-id="morphRomId"
            morph-static
            hover-motion
          />
          <div class="r-v2-stream__cover-glow" aria-hidden="true" />
        </div>
        <div class="r-v2-stream__title-block">
          <h1 class="r-v2-stream__title">{{ title }}</h1>
          <p class="r-v2-stream__subtitle">
            {{ platformLabel }} · {{ t("play.stream-subtitle") }}
          </p>
        </div>
        <RBtn
          size="x-large"
          variant="flat"
          color="primary"
          block
          prepend-icon="mdi-play"
          class="r-v2-stream__play"
          :loading="!rom || playerState === 'loading'"
          :disabled="!rom || playerState === 'loading'"
          @click="onPlay"
        >
          {{
            errorType === "occupied"
              ? t("play.stream-try-again")
              : t("play.play-on", { label: emulatorLabel })
          }}
        </RBtn>
        <div class="r-v2-stream__hero-links">
          <RBtn
            variant="text"
            size="small"
            prepend-icon="mdi-arrow-left"
            @click="backToRom"
          >
            {{ t("play.back-to-game-details") }}
          </RBtn>
          <RBtn
            variant="text"
            size="small"
            prepend-icon="mdi-view-grid-outline"
            @click="backToPlatform"
          >
            {{ t("play.back-to-gallery") }}
          </RBtn>
        </div>
      </RCard>

      <!-- Resume: preview + strip of own and shared states. Only rendered
           when this emulator has states to offer; owner chips distinguish
           states shared by other users. -->
      <RCard
        v-if="streamStates.length > 0"
        class="r-v2-stream__panel r-v2-stream__resume"
        variant="flat"
      >
        <div class="r-v2-stream__panel-head r-v2-stream__panel-head--label">
          <RIcon icon="mdi-content-save-outline" size="14" />
          <span>{{ t("play.resume-from-state") }}</span>
        </div>
        <div class="r-v2-stream__resume-body">
          <AssetPreview
            :asset="selectedState"
            type="state"
            @clear="selectedState = null"
          />
          <div class="r-v2-stream__strip-label" aria-hidden="true">
            <span>{{ t("play.all-states") }}</span>
            <span class="r-v2-stream__strip-count">{{
              streamStates.length
            }}</span>
          </div>
          <AssetStrip
            :assets="streamStates"
            type="state"
            :selected-id="selectedState?.id ?? null"
            show-owner
            @select="pickState($event as UserStateSchema)"
          />
        </div>
      </RCard>

      <!-- Session: container info + capabilities + claim errors -->
      <RCard class="r-v2-stream__panel r-v2-stream__session" variant="flat">
        <div class="r-v2-stream__panel-head r-v2-stream__panel-head--label">
          <RIcon icon="mdi-cast" size="14" />
          <span>{{ t("play.stream-subtitle") }}</span>
        </div>
        <div class="r-v2-stream__session-body">
          <RAlert
            v-if="playerState === 'error' && errorType === 'occupied'"
            type="warning"
            variant="translucent"
            :title="t('play.stream-occupied-title')"
            :text="
              occupiedBy
                ? t('play.stream-occupied-body', {
                    rom: occupiedBy.rom_name,
                    time: formatTime(occupiedBy.claimed_at),
                  })
                : t('play.stream-occupied-fallback')
            "
          />
          <RAlert
            v-else-if="playerState === 'error'"
            type="error"
            variant="translucent"
            :title="errorHint ? errorMessage : undefined"
            :text="errorHint || errorMessage"
          />

          <p class="r-v2-stream__session-hint">
            {{ t("play.streaming-description", { label: emulatorLabel }) }}
          </p>

          <p v-if="modality === 'pad'" class="r-v2-stream__session-hint">
            {{ t("play.exit-chord-hint") }}
          </p>

          <div class="r-v2-stream__session-facts">
            <div class="r-v2-stream__fact">
              <RIcon icon="mdi-gamepad-variant-outline" size="16" />
              <span class="r-v2-stream__fact-label">{{
                t("play.emulator")
              }}</span>
              <span class="r-v2-stream__fact-value">{{ emulatorLabel }}</span>
            </div>
            <div class="r-v2-stream__fact">
              <RIcon icon="mdi-content-save-outline" size="16" />
              <span class="r-v2-stream__fact-label">{{
                t("play.save-slots")
              }}</span>
              <span class="r-v2-stream__fact-value">
                {{
                  capabilities.maxSlots > 0
                    ? capabilities.maxSlots
                    : t("play.not-supported")
                }}
              </span>
            </div>
            <div class="r-v2-stream__fact">
              <RIcon icon="mdi-history" size="16" />
              <span class="r-v2-stream__fact-label">{{
                t("play.autosave")
              }}</span>
              <span class="r-v2-stream__fact-value">
                {{
                  capabilities.hasAutosave
                    ? t("play.stream-slot-n", { n: capabilities.autosaveSlot })
                    : t("play.not-supported")
                }}
              </span>
            </div>
          </div>
        </div>
      </RCard>

      <!-- Setup: default slot + fullscreen -->
      <RCard class="r-v2-stream__panel r-v2-stream__setup" variant="flat">
        <div class="r-v2-stream__panel-head r-v2-stream__panel-head--label">
          <RIcon icon="mdi-cog-outline" size="14" />
          <span>{{ t("common.settings") }}</span>
        </div>
        <div class="r-v2-stream__setup-body">
          <MemoryCardPicker
            v-if="container?.supports_memory_cards && container.emulator"
            v-model="selectedMemoryCardId"
            :emulator="container.emulator"
            :platform-id="rom?.platform_id ?? null"
          />
          <RSelect
            v-if="capabilities.maxSlots > 0"
            v-model="selectedSlot"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-content-save-outline"
            hide-details
            :label="t('play.stream-save-slot')"
            :items="slotItems"
          />
          <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
        </div>
      </RCard>
    </div>

    <!-- Running state -->
    <div
      v-else
      ref="stageRef"
      class="r-v2-stream__stage"
      :class="{ 'r-v2-stream__stage--hide-cursor': !isUIVisible }"
      role="presentation"
      @mousemove="handleMouseMove"
    >
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

      <!-- Hover sensor for cross-origin fallback: bottom only so the top
           of the stream is not blocked by an invisible trigger zone. -->
      <div class="r-v2-stream__sensor" @mousemove="handleMouseMove" />

      <!-- Auto-hiding control bar -->
      <div
        class="r-v2-stream__bar"
        :class="{ 'r-v2-stream__bar--visible': isUIVisible }"
      >
        <span class="r-v2-stream__bar-title">{{ rom?.name }}</span>
        <span class="r-v2-stream__bar-platform">{{ emulatorLabel }}</span>

        <span class="r-v2-stream__bar-spacer" />

        <RBtn
          :icon="isMuted ? 'mdi-volume-off' : 'mdi-volume-high'"
          variant="text"
          density="compact"
          :tooltip="isMuted ? t('play.stream-unmute') : t('play.stream-mute')"
          @click="toggleMute"
        />
        <RSlider
          v-model="volume"
          class="r-v2-stream__volume"
          :min="0"
          :max="100"
          :step="1"
          :disabled="isMuted"
          :aria-label="t('play.stream-volume')"
        />

        <template v-if="capabilities.maxSlots > 0">
          <RSelect
            v-model="selectedSlot"
            class="r-v2-stream__slot"
            variant="outlined"
            density="compact"
            hide-details
            :aria-label="t('play.stream-save-slot')"
            :items="slotItems"
          />
          <RBtn
            icon="mdi-content-save-outline"
            variant="text"
            density="compact"
            :tooltip="t('play.stream-save-state')"
            :loading="isSavingState"
            :disabled="stateActionBusy"
            @click="handleSaveState"
          />
          <RBtn
            icon="mdi-restore"
            variant="text"
            density="compact"
            :tooltip="t('play.stream-load-state')"
            :loading="isLoadingState"
            :disabled="stateActionBusy"
            @click="handleLoadState"
          />
          <RBtn
            v-if="capabilities.hasAutosave"
            icon="mdi-history"
            variant="text"
            density="compact"
            :tooltip="t('play.stream-load-autosave')"
            :loading="isLoadingAutosave"
            :disabled="stateActionBusy"
            @click="handleLoadAutosave"
          />
        </template>

        <RBtn
          :icon="isFullscreen ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'"
          variant="text"
          density="compact"
          :tooltip="
            isFullscreen
              ? t('play.stream-exit-fullscreen')
              : t('play.stream-fullscreen')
          "
          @click="toggleFullscreen"
        />
        <RBtn
          icon="mdi-content-save-move-outline"
          variant="text"
          density="compact"
          :tooltip="t('play.stream-save-and-exit')"
          :loading="isSavingAndExiting"
          :disabled="isSavingAndExiting"
          @click="handleSaveAndExit"
        />
        <RBtn
          icon="mdi-stop"
          variant="text"
          density="compact"
          color="error"
          :tooltip="t('play.stream-stop')"
          :disabled="isSavingAndExiting"
          @click="handleStop"
        />
      </div>
    </div>

    <!-- Exit dialog: the single confirmed way out of an active session.
         Opened by the route-leave guard (B, browser back, any link) and
         by holding Select+Start on the pad. Closing it resumes play. -->
    <RDialog
      :model-value="endedDialogOpen"
      icon="mdi-account-cancel"
      width="440"
      persistent
      @close="dismissEndedDialog"
      @update:model-value="dismissEndedDialog"
    >
      <template #header>
        <span>{{ t("play.session-ended-title") }}</span>
      </template>
      <template #content>
        <p class="r-v2-stream__exit-text">{{ endedMessage }}</p>
        <div v-if="endedReason" class="r-v2-stream__ended-reason">
          <span class="r-v2-stream__ended-reason-label">
            {{ t("play.session-ended-reason-label") }}
          </span>
          <span>{{ endedReason }}</span>
        </div>
      </template>
      <template #footer>
        <RBtn
          autofocus
          color="primary"
          variant="flat"
          @click="dismissEndedDialog"
        >
          {{ t("play.back-to-game-details") }}
        </RBtn>
      </template>
    </RDialog>

    <RDialog v-model="exitDialogOpen" width="480">
      <template #header>
        <span>{{ t("play.exit-dialog-title") }}</span>
      </template>
      <template #content>
        <p class="r-v2-stream__exit-text">
          {{
            playerState === "loading"
              ? t("play.exit-dialog-text-loading")
              : t("play.exit-dialog-text")
          }}
        </p>
      </template>
      <template #footer>
        <div class="r-v2-stream__exit-actions" @keydown="onExitDialogKeydown">
          <RBtn
            autofocus
            variant="text"
            :disabled="isSavingAndExiting || isStopping"
            @click="exitKeepPlaying"
          >
            {{ t("play.keep-playing") }}
          </RBtn>
          <RBtn
            v-if="playerState === 'loading'"
            color="error"
            variant="text"
            :loading="isStopping"
            @click="exitWithoutSaving"
          >
            {{ t("play.cancel-launch") }}
          </RBtn>
          <template v-else>
            <RBtn
              color="error"
              variant="text"
              :loading="isStopping"
              :disabled="isSavingAndExiting"
              @click="exitWithoutSaving"
            >
              {{ t("play.exit-without-saving") }}
            </RBtn>
            <RBtn
              color="primary"
              variant="flat"
              :loading="isSavingAndExiting"
              :disabled="isStopping"
              @click="exitSaveAndQuit"
            >
              {{ t("play.stream-save-and-exit") }}
            </RBtn>
          </template>
        </div>
      </template>
    </RDialog>
  </section>

  <section v-else class="r-v2-stream__loading">
    <div class="r-v2-stream__spinner" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-stream {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 32px var(--r-row-pad) 48px;
}

/* Pre-game layout: hero | session | setup. Mirrors the EmulatorJS grid
   so the two players read as siblings. */
.r-v2-stream__config {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1.4fr) minmax(
      220px,
      240px
    );
  gap: 20px;
  max-width: 1280px;
  margin: 0 auto;
  align-items: stretch;
}

/* Shared glass-panel skin: single visual vocabulary across panels. */
.r-v2-stream__panel {
  background: var(--r-color-bg-elevated) !important;
  border: 1px solid var(--r-color-border) !important;
  border-radius: var(--r-radius-lg) !important;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

.r-v2-stream__panel-head {
  padding: 14px 14px 0;
  display: flex;
  justify-content: center;
}
.r-v2-stream__panel-head--label {
  justify-content: flex-start;
  gap: 8px;
  align-items: center;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

/* ── Hero column ─────────────────────────────────────────── */
.r-v2-stream__hero {
  padding: 16px;
  gap: 12px;
  text-align: center;
}

.r-v2-stream__cover {
  position: relative;
  width: 100%;
  max-width: 220px;
  margin: 0 auto;
}
.r-v2-stream__cover-box {
  --r-cover-radius: var(--r-radius-md);
}
.r-v2-stream__cover:not(.r-v2-stream__cover--alt-art) .r-v2-stream__cover-box {
  box-shadow:
    0 18px 36px color-mix(in srgb, black 55%, transparent),
    0 0 0 1px var(--r-color-border);
}
.r-v2-stream__cover-glow {
  position: absolute;
  inset: 12px;
  background: radial-gradient(
    120% 120% at 50% 60%,
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent),
    transparent 70%
  );
  filter: blur(30px);
  z-index: -1;
  pointer-events: none;
}
.r-v2-stream__cover--alt-art .r-v2-stream__cover-glow {
  display: none;
}

.r-v2-stream__title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 4px 0;
}
.r-v2-stream__title {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}
.r-v2-stream__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-stream__play {
  margin-top: 4px;
  font-weight: var(--r-font-weight-semibold) !important;
  letter-spacing: 0.02em;
  box-shadow: 0 10px 24px
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
}
.r-v2-stream__hero-links {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid var(--r-color-border);
}

/* With states to pick from, the resume panel takes the wide middle
   column (mirrors the EmulatorJS layout) and session + setup stack in
   the right column. */
.r-v2-stream__config--resume {
  grid-template-columns: minmax(240px, 280px) minmax(0, 1.4fr) minmax(
      220px,
      260px
    );
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "hero resume session"
    "hero resume setup";
}
.r-v2-stream__config--resume .r-v2-stream__hero {
  grid-area: hero;
}
.r-v2-stream__config--resume .r-v2-stream__resume {
  grid-area: resume;
}
.r-v2-stream__config--resume .r-v2-stream__session {
  grid-area: session;
  min-height: 0;
}
.r-v2-stream__config--resume .r-v2-stream__setup {
  grid-area: setup;
}

/* ── Resume column ───────────────────────────────────────── */
.r-v2-stream__resume {
  min-height: 420px;
}
.r-v2-stream__resume-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
}
.r-v2-stream__strip-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-secondary);
  margin-top: 4px;
}
.r-v2-stream__strip-count {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--r-color-surface);
  border-radius: var(--r-radius-pill);
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
}

/* ── Session column ──────────────────────────────────────── */
.r-v2-stream__session {
  min-height: 420px;
}
.r-v2-stream__session-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
}
.r-v2-stream__session-hint {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  line-height: 1.5;
}
.r-v2-stream__session-facts {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
}
.r-v2-stream__fact {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}
.r-v2-stream__fact + .r-v2-stream__fact {
  border-top: 1px solid var(--r-color-border);
}
.r-v2-stream__fact-label {
  flex: 1;
}
.r-v2-stream__fact-value {
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

/* ── Setup column ────────────────────────────────────────── */
.r-v2-stream__setup-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

/* ── Running stage ───────────────────────────────────────── */
.r-v2-stream__stage {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}
.r-v2-stream__stage:fullscreen {
  inset: 0;
}
.r-v2-stream__stage--hide-cursor {
  cursor: none;
}

.r-v2-stream__frame {
  width: 100%;
  height: 100%;
  border: none;
  background: var(--r-color-canvas-bg-deep);
  display: block;
}

.r-v2-stream__sensor {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: 80px;
  z-index: 5;
  background: transparent;
}

/* Control bar: glass strip pinned to the bottom of the stage.
   Visibility toggles via opacity so the stream never reflows. */
.r-v2-stream__bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  min-height: 52px;
  background: color-mix(in srgb, var(--r-color-bg) 72%, transparent);
  border-top: 1px solid var(--r-color-border);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  z-index: 10;
  visibility: hidden;
  opacity: 0;
  transition:
    opacity 0.3s ease,
    visibility 0.3s ease;
  will-change: opacity;
}
.r-v2-stream__bar--visible {
  visibility: visible;
  opacity: 1;
}

.r-v2-stream__bar-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-stream__bar-platform {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
.r-v2-stream__bar-spacer {
  flex: 1;
}
.r-v2-stream__volume {
  width: 90px;
}
.r-v2-stream__slot {
  width: 110px;
  flex-shrink: 0;
}

/* ── Exit dialog ─────────────────────────────────────────── */
.r-v2-stream__exit-text {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
  line-height: 1.5;
}
.r-v2-stream__ended-reason {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: var(--r-radius-md);
  border-left: 3px solid var(--r-color-warning);
  background: var(--r-color-surface);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.r-v2-stream__ended-reason-label {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--r-color-fg-muted);
}

.r-v2-stream__exit-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

/* ── Initial ROM fetch ───────────────────────────────────── */
.r-v2-stream__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}
.r-v2-stream__spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid var(--r-color-surface-hover);
  border-top-color: var(--r-color-brand-primary);
  animation: r-stream-spin 0.8s linear infinite;
}
@keyframes r-stream-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── Responsive ──────────────────────────────────────────── */
html[data-bp~="md-and-down"] .r-v2-stream__config {
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
}
html[data-bp~="md-and-down"] .r-v2-stream__setup {
  grid-column: 1 / -1;
}
html[data-bp~="md-and-down"] .r-v2-stream__setup-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

html[data-bp~="md-and-down"] .r-v2-stream__config--resume {
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  grid-template-rows: auto;
  grid-template-areas:
    "hero resume"
    "session session"
    "setup setup";
}
html[data-bp~="md-and-down"] .r-v2-stream__resume {
  min-height: 0;
}

html[data-bp~="sm-and-down"] .r-v2-stream__config {
  grid-template-columns: 1fr;
}
html[data-bp~="sm-and-down"] .r-v2-stream__config--resume {
  grid-template-areas:
    "hero"
    "resume"
    "session"
    "setup";
}
html[data-bp~="sm-and-down"] .r-v2-stream__hero {
  flex-direction: row;
  flex-wrap: wrap;
  text-align: left;
  align-items: center;
}
html[data-bp~="sm-and-down"] .r-v2-stream__cover {
  max-width: 130px;
  flex-shrink: 0;
}
html[data-bp~="sm-and-down"] .r-v2-stream__title-block {
  flex: 1;
}
html[data-bp~="sm-and-down"] .r-v2-stream__play {
  flex: 1 1 100%;
}
html[data-bp~="sm-and-down"] .r-v2-stream__hero-links {
  flex: 1 1 100%;
  flex-direction: row;
  border-top: 1px solid var(--r-color-border);
  padding-top: 4px;
}
html[data-bp~="sm-and-down"] .r-v2-stream__bar-title,
html[data-bp~="sm-and-down"] .r-v2-stream__bar-platform {
  display: none;
}
</style>
