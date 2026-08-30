<script setup lang="ts">
// Stream: v2 player for containerized emulator streaming. A native
// emulator runs in a separate container with a Selkies WebRTC stream;
// RomM claims a session through the `/api/streaming` endpoints and
// shows the stream in an iframe pointed at the container's web UI.
//
// Layout mirrors the EmulatorJS view, three columns pre-game:
//   1. Hero: cover + title + "Play on <emulator>" CTA + back links.
//   2. Resume: the state picker and the save-data report, tabbed where
//      the emulator carries both.
//   3. Session: where the game runs and any claim errors (occupied /
//      not configured / server).
//   4. Aside: memory card picker + fullscreen-on-play.
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
  RSliderBtnGroup,
  RSwitch,
  RTooltip,
} from "@v2/lib";
import { useLocalStorage } from "@vueuse/core";
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
import type { SaveSchema, UserStateSchema } from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import streamingApi, {
  isMemoryCardImportDetail,
  type MemoryCardImport,
  type MemoryCardImportDetail,
} from "@/services/api/streaming";
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
import MemoryCardImportDialog from "@/v2/components/Player/MemoryCardImportDialog.vue";
import MemoryCardPicker from "@/v2/components/Player/MemoryCardPicker.vue";
import SaveDataPanel from "@/v2/components/Player/SaveDataPanel.vue";
import StreamStage from "@/v2/components/Player/StreamStage.vue";
import AssetStrip, {
  type AssetLayout,
} from "@/v2/components/shared/AssetStrip.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useCoverArt } from "@/v2/composables/useCoverArt";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useInputModality } from "@/v2/composables/useInputModality";
import { useMultiplayerPref } from "@/v2/composables/useMultiplayerPref";
import { usePageTitle } from "@/v2/composables/usePageTitle";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import type { SliderBtnGroupItem } from "@/v2/lib/primitives/RSliderBtnGroup/types";
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
const { multiplayerOnPlay } = useMultiplayerPref();
const { modality } = useInputModality();
const playSession = usePlaySession();

const rom = ref<DetailedRom | null>(null);
const playerState = ref<PlayerState>("idle");
const errorType = ref<ErrorType>(null);
const errorMessage = ref<string>("");
const errorHint = ref<string>("");
const occupiedBy = ref<{ rom_name: string; claimed_at: string } | null>(null);
const launchPhase = ref<string | null>(null);
const draining = ref(false);
const containerHost = ref<string>("");
const isSavingAndExiting = ref(false);
const isSavingState = ref(false);
const isLoadingState = ref(false);
const volume = ref(100);
const isMuted = ref(false);
// Set from a 428 on claim: the container holds a memory card nobody has
// decided about yet. The claim is not held open, the answer is replayed on a
// fresh one.
const cardImportDetail = ref<MemoryCardImportDetail | null>(null);
const showCardImport = ref(false);
const showDiscSwap = ref(false);
const selectedDisc = ref<number | null>(null);
const isSwappingDisc = ref(false);

const gameRunning = computed(() => playerState.value === "playing");

// Set by the Join action on the game page. A join attaches to a session
// someone else is hosting instead of claiming a container, so none of the
// claim's setup (state resume, memory card, card import) applies, and none
// of the owner-only controls do either.
//
// Read once rather than kept reactive: useRoute() has already advanced to the
// destination by the time the teardown guards below run, so a live computed
// reports false on the way out and a joiner's unmount would release the
// host's session out from under them.
const isJoining = route.query.join === "1";

// True only while this tab's own claim is held. The teardown paths key off
// this rather than the player state, because a joiner reaches "playing" too.
const holdsClaim = ref(false);

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

watch(
  () => playerState.value === "loading",
  (launching) => {
    if (launching) startLaunchPoll();
    else stopLaunchPoll();
  },
);

// What the play button says while the claim is in flight. The phase only
// arrives once the broker has started unpacking, so the generic line covers
// both the wait before that and every launch with no extraction step.
const launchStatusText = computed(() => {
  if (launchPhase.value === "extracting_archive") {
    return t("play.launch-extracting-archive");
  }
  if (launchPhase.value === "extracting_pkg") {
    return t("play.launch-extracting-pkg");
  }
  return t("play.launch-starting");
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

// Emulators that keep saves in the emulated filesystem rather than in
// snapshots get no slots from the backend. There is nothing to pick from
// and never will be, so the picker gives way to a report of the save
// archive instead of an empty grid.
const supportsStates = computed(
  () => capabilities.value.maxSlots > 0 || capabilities.value.hasAutosave,
);

function fileExtension(name: string): string {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

// Mirrors the backend's Rom.has_m3u_file(): the emulator's disc-swap menu
// only exists for multi-disc sets that ship a playlist.
const hasM3uFile = computed(() =>
  (rom.value?.files ?? []).some((f) => fileExtension(f.file_name) === "m3u"),
);

// Mirrors the download endpoint's playlist filtering: when .cue files are
// present only those are valid swap targets (raw .bin tracks are not), and
// the .m3u itself is never something to swap to.
const discOptions = computed(() => {
  const files = (rom.value?.files ?? []).filter(
    (f) => fileExtension(f.file_name) !== "m3u",
  );
  const cueFiles = files.filter((f) => fileExtension(f.file_name) === "cue");
  const listed = cueFiles.length > 0 ? cueFiles : files;
  return listed.map((f) => ({ title: f.file_name, value: f.id }));
});

// A rom with a single swappable disc has nothing to swap to, whatever the
// platform can do.
const canSwapDisc = computed(
  () =>
    capabilities.value.supportsDiscSwap &&
    discOptions.value.length > 1 &&
    hasM3uFile.value &&
    !isJoining,
);

// Platforms whose emulator changes discs from its own menu get a note
// instead of a control.
const showManualDiscHint = computed(
  () =>
    capabilities.value.hasManualDiscSwap &&
    (rom.value?.files?.length ?? 0) > 1 &&
    !isJoining,
);

// ── Resume-from-state picker ────────────────────────────────────────
// States the container's emulator can resume from: the user's own plus
// other users' public ones (that is what all_user_states carries), kept
// to this emulator's namespace so EmulatorJS states stay out. The list
// arrives newest-first from the backend.
const selectedState = ref<UserStateSchema | null>(null);

// The archives the broker syncs, newest-first from the backend, scoped
// to this emulator the same way the states are.
const emulatorSaves = computed<SaveSchema[]>(() => {
  const emulator = container.value?.emulator?.toLowerCase();
  if (!rom.value || !emulator) return [];
  return (rom.value.user_saves ?? []).filter(
    (s) => (s.emulator ?? "").toLowerCase() === emulator,
  );
});

// The one the broker restores before boot.
const newestSave = computed<SaveSchema | null>(
  () => emulatorSaves.value[0] ?? null,
);

const streamStates = computed<UserStateSchema[]>(() => {
  const emulator = container.value?.emulator?.toLowerCase();
  if (!rom.value || !emulator) return [];
  return (rom.value.all_user_states ?? []).filter(
    (s) => (s.emulator ?? "").toLowerCase() === emulator,
  );
});

// Every capture is kept, so a heavy save-stater ends up with a history the
// horizontal strip buries. Grid and list trade thumbnail size for how many
// entries fit at once; the choice sticks across sessions.
const STATE_LAYOUTS = [
  { value: "strip", icon: "mdi-view-carousel-outline" },
  { value: "grid", icon: "mdi-view-grid-outline" },
  { value: "list", icon: "mdi-view-list" },
] as const satisfies readonly { value: AssetLayout; icon: string }[];

const stateLayout = useLocalStorage<AssetLayout>(
  "romm:v2:stream:states-layout",
  "strip",
);

// Preselect the newest state once so Play resumes where the user left off.
// A deliberate clear (deselect or the preview's clear button) sticks: the
// list recomputes on every rom/config refresh and must not re-pick.
const statePreselected = ref(false);
watch(
  streamStates,
  (states) => {
    const current = selectedState.value;
    if (current && !states.some((s) => s.id === current.id)) {
      selectedState.value = null;
    }
    if (!statePreselected.value && states.length > 0) {
      statePreselected.value = true;
      if (!selectedState.value) selectedState.value = states[0];
    }
  },
  { immediate: true },
);

// Clicking the selected tile deselects it, which is how a fresh boot is
// chosen when a state exists.
function pickState(state: UserStateSchema): void {
  selectedState.value = selectedState.value?.id === state.id ? null : state;
}

function clearState(): void {
  selectedState.value = null;
}

// ── Resume tabs ─────────────────────────────────────────────────────
// A container can carry both a state library and a save archive, and
// they resume different things: a snapshot picks up mid-frame, the
// archive only puts the game's own save file back on disk. Where both
// exist the panel tabs between them.
type ResumeTab = "state" | "save";

const resumeTab = ref<ResumeTab>("state");

const showResumeTabs = computed(
  () => supportsStates.value && emulatorSaves.value.length > 0,
);

// The pick only counts when there is something to pick between.
const activeResumeTab = computed<ResumeTab>(() => {
  if (!supportsStates.value) return "save";
  return showResumeTabs.value ? resumeTab.value : "state";
});

function setResumeTab(id: ResumeTab): void {
  resumeTab.value = id;
}

const resumeTabs = computed<SliderBtnGroupItem<ResumeTab>[]>(() => [
  {
    id: "state",
    label: t("common.states"),
    badge: streamStates.value.length,
    icon: "mdi-file",
  },
  {
    id: "save",
    label: t("common.saves"),
    badge: emulatorSaves.value.length,
    icon: "mdi-content-save",
  },
]);

// ── Memory card picker (whole-card sync) ────────────────────────────
// Which card to hydrate onto the container at claim. Only shown for
// containers that sync whole cards (PCSX2). Null means "let the backend
// pick the newest / auto-create a blank one". MemoryCardPicker owns the
// fetch + default-newest selection; we just carry the id to claim.
const selectedMemoryCardId = ref<number | null>(null);

// RomM keeps every capture, so slots are no longer a user-facing concept:
// they are just the register the emulator writes through. Everything rides
// the autosave slot, which is also what hydration pushes into and what
// save-and-exit already uses, so quick-load in game lands on the same file
// the picker last sent down.
const streamSlot = computed(() => capabilities.value.autosaveSlot);

const title = computed(
  () => heroRom.value?.name || heroRom.value?.fs_name_no_ext || "",
);

usePageTitle(() =>
  title.value ? t("play.page-title", { name: title.value }) : null,
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

let heartbeatInFlight = false;

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
  // A joiner holds no claim, so the stamp is not theirs to refresh and the
  // route would 403 on every tick. The socket beat above still runs: they
  // are playing, and the activity panel should say so.
  // A slow round-trip must not let the next tick stack a second request.
  if (sessionActive.value && !isJoining && !heartbeatInFlight) {
    heartbeatInFlight = true;
    try {
      await handleSessionStatus(
        await streamingStore.heartbeatSession(rom.value.platform_slug),
      );
    } finally {
      heartbeatInFlight = false;
    }
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
  await stage.value?.leaveFullscreen();

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
  // The status route belongs to the claim holder; a joiner would only
  // collect 403s and then be thrown out of a session that is still running.
  if (isJoining) return;
  if (sessionPollTimer) return;
  sessionPollTimer = setInterval(pollSessionStatus, SESSION_POLL_MS);
}

function stopSessionPoll() {
  if (sessionPollTimer) {
    clearInterval(sessionPollTimer);
    sessionPollTimer = null;
  }
}

// The claim request blocks until the game is up, and a webstation broker
// unpacks pkg and archive ROMs before it can start the emulator. Minutes can
// pass with nothing to show, so the phase comes from a second request running
// alongside the claim.
const LAUNCH_POLL_MS = 3_000;
let launchPollTimer: ReturnType<typeof setInterval> | null = null;

async function pollLaunchPhase(): Promise<void> {
  if (!rom.value) return;
  const status = await streamingStore.fetchSessionStatus(
    rom.value.platform_slug,
  );
  // Only the phase is read here. The claim is not recorded until the request
  // this runs beside has reached the backend, so an early poll reports the
  // session as ended, and acting on that would tear down a live launch.
  if (playerState.value !== "loading") return;
  launchPhase.value = status?.extraction_phase ?? null;
}

function startLaunchPoll() {
  // A joiner does not own the claim, so the status route only gives it 403s.
  if (launchPollTimer || isJoining) return;
  launchPollTimer = setInterval(() => void pollLaunchPhase(), LAUNCH_POLL_MS);
}

function stopLaunchPoll() {
  if (launchPollTimer) {
    clearInterval(launchPollTimer);
    launchPollTimer = null;
  }
  launchPhase.value = null;
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

// ── Stage ──────────────────────────────────────────────────────────
// The iframe, the auto-hiding bar and the focus handling all live in
// StreamStage; this view only supplies the bar's buttons.
const stage = ref<InstanceType<typeof StreamStage> | null>(null);

function focusStream(): void {
  stage.value?.focusStream();
}

// ── Volume / mute ───────────────────────────────────────────────────
// A same-origin container takes both straight from the browser, moving this
// viewer's own output rather than the mixer every viewer shares. The broker
// path is what is left for cross-origin containers, and it stays debounced so
// the broker only hears the value once it settles.
let volumeDebounce: ReturnType<typeof setTimeout> | null = null;

function sendVolumeToBroker(level: number): void {
  if (volumeDebounce) clearTimeout(volumeDebounce);
  volumeDebounce = setTimeout(() => {
    const platform = rom.value?.platform_slug;
    if (platform)
      streamingApi
        .setVolume(platform, level)
        .catch((err) => console.warn("[streaming] Could not set volume:", err));
  }, 150);
}

watch(volume, (val) => {
  const level = Math.round(val);
  if (stage.value?.postToStream({ type: "setVolume", value: level / 100 }))
    return;
  sendVolumeToBroker(level);
});

function toggleMute(): void {
  isMuted.value = !isMuted.value;
  if (stage.value?.postToStream({ type: "setMute", value: isMuted.value }))
    return;
  const platform = rom.value?.platform_slug;
  if (platform)
    streamingApi
      .setMute(platform, isMuted.value)
      .catch((err) => console.warn("[streaming] Could not set mute:", err));
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

// `cardImport` is only set when this run is the retry after the memory card
// import prompt; the backend rejects the claim again without it.
async function onPlay(cardImport?: MemoryCardImport): Promise<void> {
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
    if (isJoining) {
      const joined = await streamingStore.joinSession(rom.value.platform_slug);
      await flourish;
      if ((playerState.value as PlayerState) === "exited") return;
      containerHost.value = joined.host;
      playerState.value = "playing";
      if (fullscreenOnPlay.value) {
        await nextTick();
        await stage.value?.enterFullscreen();
      }
    } else {
      // The backend derives the ROM's filesystem path and platform from the id.
      // A selected state rides along: its file is pushed to the broker and the
      // emulator loads it once the game is up.
      const session = await streamingStore.claimSession(
        rom.value.id,
        selectedState.value?.id,
        container.value?.supports_memory_cards
          ? (selectedMemoryCardId.value ?? undefined)
          : undefined,
        cardImport,
        multiplayerOnPlay.value,
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
        // so release it again instead of entering the playing state. Nobody
        // played anything, so there is nothing worth saving over their pick.
        const released = await streamingStore.releaseSession(
          rom.value.platform_slug,
          false,
        );
        if (!released) {
          snackbar.error(t("play.stream-release-failed"), { timeout: 6000 });
        }
        return;
      }
      holdsClaim.value = true;
      containerHost.value = session.host;
      playerState.value = "playing";

      if (fullscreenOnPlay.value) {
        await nextTick();
        await stage.value?.enterFullscreen();
      }
    }
  } catch (err: unknown) {
    // Same race the success path guards: the user can leave via the exit
    // dialog while the claim is in flight. Nothing was claimed here, so
    // just stay exited rather than resurrecting the launch screen.
    if ((playerState.value as PlayerState) === "exited") {
      return;
    }

    // The store propagates the raw axios error; the status and the
    // backend's detail payload live on its response.
    const status = isAxiosError(err) ? err.response?.status : undefined;
    const detail: unknown = isAxiosError(err)
      ? err.response?.data?.detail
      : undefined;

    // Nothing was claimed and nothing is broken, the launch is just waiting
    // on the user's answer, so this is a prompt rather than an error state.
    if (status === 428 && isMemoryCardImportDetail(detail)) {
      playerState.value = "idle";
      cardImportDetail.value = detail;
      showCardImport.value = true;
      return;
    }

    // A join races the host: they can close the session or end it between
    // the game page listing it and this request landing.
    if (isJoining && (status === 403 || status === 404)) {
      // The list that offered this Join is now known to be wrong, so drop the
      // entry rather than leaving the affordance up on the page behind.
      if (rom.value) streamingStore.forgetJoinableSession(rom.value.id);
      playerState.value = "error";
      errorType.value = "server";
      errorMessage.value = t(
        status === 403 ? "play.join-closed" : "play.join-ended",
      );
      errorHint.value = "";
      return;
    }

    playerState.value = "error";

    if (status === 409) {
      errorType.value = "occupied";
      const busy =
        detail && typeof detail === "object"
          ? (detail as {
              rom_name: string | null;
              claimed_at: string | null;
              draining?: boolean;
            })
          : null;
      // A draining container is nobody's: the previous session is over and its
      // exit state is still being collected, so there is no holder to name.
      draining.value = busy?.draining === true;
      occupiedBy.value =
        busy && busy.rom_name && busy.claimed_at
          ? { rom_name: busy.rom_name, claimed_at: busy.claimed_at }
          : null;
    } else if (status === 404) {
      // 404 covers two cases: no container configured for the platform,
      // and the ROM itself missing (deleted between fetch and claim). The
      // config the view already holds says which, rather than the wording of
      // the backend's detail string.
      if (container.value) {
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
      // The axios message ("Request failed with status code 502") is English
      // and says nothing the hint does not, so the title stays translated and
      // the status carries the detail.
      errorMessage.value = t("play.stream-error-generic");
      errorHint.value = hintForStatus(status);
    }
  }

  // Start timing the session once the claim succeeds and playback is live.
  // The session is ingested on unmount, which updates last_played /
  // now_playing / status server-side.
  if (rom.value && playerState.value === "playing") {
    playSession.start(rom.value);
  }
}

function onCardImportAnswer(answer: MemoryCardImport): void {
  cardImportDetail.value = null;
  void onPlay(answer);
}

// Cancelling leaves the container untouched and unclaimed, so there is
// nothing to release; just go back where the user came from.
function onCardImportCancel(): void {
  cardImportDetail.value = null;
  backToRom();
}

async function performStop(): Promise<void> {
  // Both the control bar and the exit dialog land here, and the release takes
  // long enough for a second press to arrive mid-flight; the second DELETE
  // would hit a key the first one already freed, or one a new claim now owns.
  if (isStopping.value) return;
  isStopping.value = true;
  try {
    // Leaving as a joiner ends nothing: the host keeps the container, so the
    // only thing to do is drop this tab out of the room.
    if (holdsClaim.value) {
      // This is the deliberate way out without saving, so no state is written.
      // The in-game save data still travels back either way.
      const released = await streamingStore.releaseSession(
        rom.value?.platform_slug ?? "",
        false,
      );
      // The claim only goes when the backend says it went. Left standing, it
      // tells the user why the container is still busy and gives the unmount
      // release something to retry.
      holdsClaim.value = !released;
      if (!released) {
        snackbar.error(t("play.stream-release-failed"), { timeout: 6000 });
      }
    }
    playerState.value = "exited";
    containerHost.value = "";
  } finally {
    isStopping.value = false;
  }
}

async function handleStop(): Promise<void> {
  await performStop();
  backToRom();
}

// The thumbnail for the state about to be written. Best effort: without it the
// state falls back to whatever frame the emulator can produce for itself, and
// some cores cannot produce one at all without deadlocking.
async function pushStreamFrame(): Promise<void> {
  if (!rom.value) return;
  try {
    const frame = await stage.value?.captureFrame();
    if (frame) await streamingApi.putStateFrame(rom.value.platform_slug, frame);
  } catch (err) {
    console.warn("[streaming] Could not capture stream frame:", err);
  }
}

async function performSaveAndExit(): Promise<void> {
  if (!rom.value || playerState.value !== "playing") return;
  // The broker's save+kill runs for seconds with the player still on screen,
  // so the guard is on the flag rather than on the state it eventually sets.
  if (isSavingAndExiting.value || isStopping.value) return;
  // A joiner has no claim to save or release, and the host's game keeps
  // running after they leave.
  if (!holdsClaim.value) {
    playerState.value = "exited";
    containerHost.value = "";
    return;
  }
  isSavingAndExiting.value = true;
  let saved = false;
  let released = false;
  try {
    await pushStreamFrame();
    const result = await streamingStore.saveAndExit(
      rom.value.platform_slug,
      capabilities.value.autosaveSlot,
      true,
    );
    saved = result.saved;
    released = result.released;
    if (!released) {
      // The save-and-exit request failed, so the claim may still be held;
      // fall back to a plain release so the container is freed before the
      // player is marked exited.
      released = await streamingStore.releaseSession(rom.value.platform_slug);
    }
  } finally {
    isSavingAndExiting.value = false;
    holdsClaim.value = !released;
    playerState.value = "exited";
    containerHost.value = "";
  }
  if (!released) {
    snackbar.error(t("play.stream-release-failed"), { timeout: 6000 });
  }
  // Without states there is no save to confirm: the exit dumps the in-game
  // save archive instead, so an unconfirmed state is the expected answer.
  if (!saved && supportsStates.value) {
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
  if (!rom.value || playerState.value !== "playing" || isJoining) return;
  if (isSavingState.value) return;
  isSavingState.value = true;
  try {
    await pushStreamFrame();
    await streamingApi.saveState(rom.value.platform_slug, streamSlot.value);
  } catch (err) {
    console.warn("[streaming] Could not save state:", err);
    snackbar.error(t("play.stream-save-state-failed"), { timeout: 6000 });
  } finally {
    isSavingState.value = false;
  }
}

async function handleLoadState(): Promise<void> {
  if (!rom.value || playerState.value !== "playing" || isJoining) return;
  if (isLoadingState.value) return;
  isLoadingState.value = true;
  try {
    await streamingApi.loadState(rom.value.platform_slug, streamSlot.value);
  } catch (err) {
    console.warn("[streaming] Could not load state:", err);
    snackbar.error(t("play.stream-load-state-failed"), { timeout: 6000 });
  } finally {
    isLoadingState.value = false;
  }
}

function openDiscSwap(): void {
  selectedDisc.value = null;
  showDiscSwap.value = true;
}

async function handleSwapDisc(): Promise<void> {
  if (!rom.value || selectedDisc.value === null || isSwappingDisc.value) return;
  isSwappingDisc.value = true;
  try {
    await streamingApi.swapDisc(rom.value.platform_slug, selectedDisc.value);
    showDiscSwap.value = false;
  } catch (err) {
    console.warn("[streaming] Could not swap disc:", err);
    snackbar.error(t("play.swap-disc-failed"), { timeout: 6000 });
  } finally {
    isSwappingDisc.value = false;
  }
}

const stateActionBusy = computed(
  () =>
    isSavingState.value ||
    isLoadingState.value ||
    isSavingAndExiting.value ||
    isSwappingDisc.value,
);

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
  await stage.value?.leaveFullscreen();
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
  await performStop();
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
  // The claim, not the player state, says whether anything is still held: an
  // exit whose release failed is "exited" and still holding the container.
  // Nothing of the host's to tear down either way, and the keepalive routes
  // are owner-only.
  if (!holdsClaim.value) {
    playerState.value = "exited";
    return;
  }
  const platform = rom.value?.platform_slug ?? "";
  if (playerState.value === "playing") {
    streamingStore.saveAndExitKeepalive(
      platform,
      capabilities.value.autosaveSlot,
    );
  } else {
    // Still loading, or exited with a release that failed: nothing to save,
    // and this is the last chance to hand the container back.
    streamingStore.releaseSessionKeepalive(platform);
  }
  // Guards the in-app unmount path from double-releasing if the page
  // comes back from the bfcache and is then navigated normally.
  holdsClaim.value = false;
  playerState.value = "exited";
}

onMounted(async () => {
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

  // A join is confirmed on the game page, so there is no start page left to
  // show: the settings on it (resume state, memory card, multiplayer) all
  // belong to the claim, and a joiner makes none of those choices.
  if (isJoining) {
    // Reaching this URL directly can beat the app-level config fetch, and
    // onPlay reads the container out of it.
    if (!container.value) await streamingStore.fetchConfig();
    void onPlay();
    return;
  }

  // Autofocus the Play CTA so gamepad/keyboard users land on the
  // primary action without an extra Tab.
  if (modality.value === "pad" || modality.value === "key") {
    await nextTick();
    focusPlayButton();
  }
});

onBeforeUnmount(() => {
  // Every exit path (Stop, Save & Exit, back nav) unmounts the view, so this
  // is the single choke point for recording the session.
  playSession.flush();
  playingStore.setPlaying(false);
  document.removeEventListener("visibilitychange", onVisibilityChange);
  window.removeEventListener("pagehide", onPageHide);
  if (volumeDebounce) clearTimeout(volumeDebounce);
  if (chordRaf) {
    cancelAnimationFrame(chordRaf);
    chordRaf = 0;
  }
  stopActivityHeartbeat();
  stopSessionPoll();
  stopLaunchPoll();
  emitActivityStop();
  // The claim, not the player state, says whether anything is still held:
  // an exit whose release failed leaves it standing, and this is its retry.
  if (!holdsClaim.value) return;
  if (playerState.value === "playing") {
    // Navigation away while a game is active: fire save+kill in the
    // broker background so navigation is never held up.
    void streamingStore.saveAndExit(
      rom.value?.platform_slug ?? "",
      capabilities.value.autosaveSlot,
      false,
    );
  } else {
    // Nothing is running, so there is nothing worth a state: asking for one
    // here would only file whatever the last session left in the slot.
    void streamingStore.releaseSession(rom.value?.platform_slug ?? "", false);
  }
});
</script>

<template>
  <section v-if="rom || heroSeed" class="r-v2-stream">
    <!-- Pre-game configuration -->
    <div v-if="!gameRunning" class="r-v2-stream__config">
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
            style-context="player"
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
          :prepend-icon="playerState === 'loading' ? 'mdi-loading' : 'mdi-play'"
          class="r-v2-stream__play"
          :class="{ 'r-v2-stream__play--launching': playerState === 'loading' }"
          :disabled="!rom || playerState === 'loading'"
          @click="onPlay()"
        >
          {{
            playerState === "loading"
              ? launchStatusText
              : errorType === "occupied"
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

      <!-- Resume: preview + strip of own and shared states. Always present
           so a first run and a long history read as the same screen; the
           strip carries its own empty state. Owner chips distinguish states
           shared by other users. The save archive shares the cell, tabbed
           where the emulator has both. -->
      <RCard class="r-v2-stream__panel r-v2-stream__resume" variant="flat">
        <div
          class="r-v2-stream__panel-head"
          :class="{ 'r-v2-stream__panel-head--label': !showResumeTabs }"
        >
          <RSliderBtnGroup
            v-if="showResumeTabs"
            variant="tab"
            :model-value="activeResumeTab"
            :items="resumeTabs"
            :aria-label="t('rom.load-save-or-state')"
            @update:model-value="setResumeTab"
          />
          <template v-else>
            <RIcon icon="mdi-content-save-outline" size="14" />
            <span>{{
              activeResumeTab === "state"
                ? t("play.resume-from-state")
                : t("play.save-data")
            }}</span>
          </template>
        </div>
        <div class="r-v2-stream__resume-body">
          <template v-if="activeResumeTab === 'state'">
            <AssetPreview
              :asset="selectedState"
              type="state"
              :show-heading="false"
              @clear="clearState"
            />
            <div class="r-v2-stream__strip-label">
              <span aria-hidden="true">{{ t("play.all-states") }}</span>
              <span class="r-v2-stream__strip-count" aria-hidden="true">{{
                streamStates.length
              }}</span>
              <div
                class="r-v2-stream__strip-views"
                role="group"
                :aria-label="t('play.states-view')"
              >
                <RBtn
                  v-for="view in STATE_LAYOUTS"
                  :key="view.value"
                  variant="text"
                  size="x-small"
                  :icon="view.icon"
                  :aria-pressed="stateLayout === view.value"
                  :class="{
                    'r-v2-stream__strip-view--on': stateLayout === view.value,
                  }"
                  :aria-label="t(`play.states-view-${view.value}`)"
                  @click="stateLayout = view.value"
                />
              </div>
            </div>
            <AssetStrip
              :assets="streamStates"
              type="state"
              :selected-id="selectedState?.id ?? null"
              :layout="stateLayout"
              show-owner
              @select="pickState($event as UserStateSchema)"
            />
          </template>

          <!-- The archive is reported, not offered: loading it is the
               game's own job. -->
          <SaveDataPanel v-else :save="newestSave" :platform="platformLabel" />
        </div>
      </RCard>

      <!-- Session: container info + claim errors -->
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
              draining
                ? t('play.stream-occupied-draining')
                : occupiedBy
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
          </div>
        </div>
      </RCard>

      <!-- Aside: the panels stack as one grid cell, so the memory card
           section can come and go without leaving a hole in the layout. -->
      <div class="r-v2-stream__aside">
        <!-- Memory cards: their own section, since a card is picked per run
             and has nothing to do with the client-side preferences below. -->
        <RCard
          v-if="container?.supports_memory_cards && container.emulator"
          class="r-v2-stream__panel r-v2-stream__cards"
          variant="flat"
        >
          <div class="r-v2-stream__panel-head r-v2-stream__panel-head--label">
            <RIcon icon="mdi-sd" size="14" />
            <span>{{ t("play.memory-card") }}</span>
          </div>
          <div class="r-v2-stream__cards-body">
            <MemoryCardPicker
              v-model="selectedMemoryCardId"
              :emulator="container.emulator"
              :platform-id="rom?.platform_id ?? null"
            />
          </div>
        </RCard>

        <!-- Setup: client-side play preferences -->
        <RCard class="r-v2-stream__panel r-v2-stream__setup" variant="flat">
          <div class="r-v2-stream__panel-head r-v2-stream__panel-head--label">
            <RIcon icon="mdi-cog-outline" size="14" />
            <span>{{ t("common.settings") }}</span>
          </div>
          <div class="r-v2-stream__setup-body">
            <RSwitch
              v-model="fullscreenOnPlay"
              :label="t('play.full-screen')"
            />
            <!-- Fixed for the session: the backend reads it at claim time. -->
            <div class="r-v2-stream__setup-item">
              <RSwitch
                v-model="multiplayerOnPlay"
                :label="t('play.multiplayer')"
              />
              <span class="r-v2-stream__setup-hint">
                {{ t("play.multiplayer-hint") }}
              </span>
            </div>
          </div>
        </RCard>
      </div>
    </div>

    <!-- Running state -->
    <StreamStage
      v-else
      ref="stage"
      :src="containerHost"
      :frame-title="t('play.stream-frame-title')"
      :active="gameRunning"
    >
      <template #bar="{ isFullscreen, toggleFullscreen }">
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

        <!-- States and the save-and-exit belong to the claim holder. -->
        <template v-if="capabilities.hasAutosave && !isJoining">
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
        </template>

        <RBtn
          v-if="canSwapDisc"
          icon="mdi-disc"
          variant="text"
          density="compact"
          :tooltip="t('play.stream-swap-disc')"
          :loading="isSwappingDisc"
          :disabled="stateActionBusy"
          @click="openDiscSwap"
        />
        <span
          v-else-if="showManualDiscHint"
          class="r-v2-stream__disc-hint"
          role="img"
          :aria-label="t('play.manual-disc-swap-hint')"
        >
          <RIcon icon="mdi-disc-alert" size="small" />
          <RTooltip
            activator="parent"
            :text="t('play.manual-disc-swap-hint')"
          />
        </span>

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
          v-if="!isJoining"
          icon="mdi-content-save-move-outline"
          variant="text"
          density="compact"
          :tooltip="t('play.stream-save-and-exit')"
          :loading="isSavingAndExiting"
          :disabled="isSavingAndExiting"
          @click="handleSaveAndExit"
        />
        <RBtn
          :icon="isJoining ? 'mdi-exit-to-app' : 'mdi-stop'"
          variant="text"
          density="compact"
          color="error"
          :tooltip="isJoining ? t('play.leave-session') : t('play.stream-stop')"
          :disabled="isSavingAndExiting"
          @click="handleStop"
        />
      </template>
    </StreamStage>

    <!-- One-time prompt for the card the container was already holding.
         Answering it retries the claim; cancelling goes back. -->
    <MemoryCardImportDialog
      v-model="showCardImport"
      :detail="cardImportDetail"
      @adopt="onCardImportAnswer('adopt')"
      @discard="onCardImportAnswer('discard')"
      @cancel="onCardImportCancel"
    />

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
        <span>{{
          isJoining ? t("play.leave-dialog-title") : t("play.exit-dialog-title")
        }}</span>
      </template>
      <template #content>
        <p class="r-v2-stream__exit-text">
          {{
            isJoining
              ? t("play.leave-dialog-text")
              : playerState === "loading"
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
            v-if="isJoining"
            color="error"
            variant="text"
            :loading="isStopping"
            @click="exitWithoutSaving"
          >
            {{ t("play.leave-session") }}
          </RBtn>
          <RBtn
            v-else-if="playerState === 'loading'"
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

    <RDialog v-model="showDiscSwap" width="440">
      <template #header>
        <span>{{ t("play.swap-disc-title") }}</span>
      </template>
      <template #content>
        <p class="r-v2-stream__exit-text">{{ t("play.swap-disc-text") }}</p>
        <RSelect
          v-model="selectedDisc"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-disc"
          hide-details
          :label="t('rom.file')"
          :items="discOptions"
        />
      </template>
      <template #footer>
        <RBtn
          variant="text"
          :disabled="isSwappingDisc"
          @click="showDiscSwap = false"
        >
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn
          color="primary"
          variant="flat"
          :loading="isSwappingDisc"
          :disabled="selectedDisc === null"
          @click="handleSwapDisc"
        >
          {{ t("play.swap-disc-confirm") }}
        </RBtn>
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

/* Pre-game layout: hero | resume | session over aside. Mirrors the
   EmulatorJS grid so the two players read as siblings. */
.r-v2-stream__config {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1.4fr) minmax(
      220px,
      260px
    );
  grid-template-rows: 1fr auto;
  grid-template-areas:
    "hero resume session"
    "hero resume aside";
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
  grid-area: hero;
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
  white-space: normal;
  text-wrap: balance;
  line-height: 1.25;
  min-height: 3.25em;
  height: auto;
  box-shadow: 0 10px 24px
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
}
.r-v2-stream__play--launching :deep(.v-icon) {
  animation: r-stream-spin 0.8s linear infinite;
}
.r-v2-stream__hero-links {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid var(--r-color-border);
}

.r-v2-stream__aside {
  grid-area: aside;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

/* ── Resume column ───────────────────────────────────────── */
.r-v2-stream__resume {
  grid-area: resume;
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
.r-v2-stream__strip-views {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 2px;
}
.r-v2-stream__strip-view--on {
  color: var(--r-color-brand-primary);
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
  grid-area: session;
  min-height: 0;
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
.r-v2-stream__cards-body,
.r-v2-stream__setup-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}
.r-v2-stream__setup-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-stream__setup-hint {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  line-height: 1.35;
}

/* ── Running stage ───────────────────────────────────────── */
/* The stage itself lives in StreamStage; these style the bar's contents,
   which are slotted in from here and so carry this scope. */
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
.r-v2-stream__disc-hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: var(--r-color-fg-muted);
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
  grid-template-rows: auto;
  grid-template-areas:
    "hero resume"
    "session session"
    "aside aside";
}
html[data-bp~="md-and-down"] .r-v2-stream__aside {
  grid-column: 1 / -1;
}
html[data-bp~="md-and-down"] .r-v2-stream__setup-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

html[data-bp~="md-and-down"] .r-v2-stream__resume {
  min-height: 0;
}

html[data-bp~="sm-and-down"] .r-v2-stream__config {
  grid-template-columns: 1fr;
  grid-template-areas:
    "hero"
    "resume"
    "session"
    "aside";
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
