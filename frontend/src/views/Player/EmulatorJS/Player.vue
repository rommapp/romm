<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, onUnmounted, ref } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import { useTheme } from "vuetify";
import type {
  FirmwareSchema,
  SaveSchema,
  StateSchema,
  NetplayICEServer,
} from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import { saveApi as api } from "@/services/api/save";
import pendingAssetStore, {
  pendingAssetId,
  type PendingAsset,
} from "@/services/pending-asset";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeLanguage from "@/stores/language";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import {
  areThreadsRequiredForEJSCore,
  getSupportedEJSCores,
  getControlSchemeForPlatform,
  getDownloadPath,
} from "@/utils";
import {
  saveSave,
  captureScreenshot,
  dumpSaveFile,
  exitEmulatorOnce,
  resolveScreenshot,
  storedScreenshotFor,
  saveState,
  loadEmulatorJSSave,
  loadEmulatorJSState,
  invalidateEmulatorJSRomCacheIfRenamed,
  installEJSDefaultOptionsTrap,
  createQuickLoadButton,
  createSaveQuitButton,
  createExitEmulationButton,
  createSaveSyncTracker,
  bytesEqual,
  pollSaveFiles,
  saveSaveOnUnload,
  toArrayBuffer,
} from "./utils";

const INVALID_CHARS_REGEX = /[#<$+%>!`&*'|{}/\\?"=@:^\r\n]/gi;

const authStore = storeAuth();
const romsStore = storeRoms();
const playingStore = storePlaying();
const configStore = storeConfig();
const languageStore = storeLanguage();
const router = useRouter();

const props = defineProps<{
  rom: DetailedRom;
  save: SaveSchema | null;
  state: StateSchema | null;
  bios: FirmwareSchema | null;
  core: string | null;
  disc: number | null;
  /** Slot for new saves when the loaded save has none; defaults to autosave. */
  saveSlot?: string | null;
}>();
const romRef = ref<DetailedRom>(props.rom);
// The save the session booted from, and the version this session has written
// so far. Loading a save resets the version so the next write opens a new one.
let loadedSave: SaveSchema | null = props.save;
const sessionSaveRef = ref<SaveSchema | null>(null);
const deviceIDRef = ref(authStore.user?.current_device_id ?? undefined);
// Bytes the server already holds, so forced writes can skip an unchanged SRAM.
const saveTracker = createSaveSyncTracker();
function baselineSaveTrackerFromEmulator() {
  saveTracker.baseline(dumpSaveFile());
}
// Writes run one at a time so concurrent writers cannot both open a version;
// loading a save bumps the generation, which voids writes queued before it,
// and bytes read while a load is in flight are stale, so they are dropped.
let saveWrite: Promise<unknown> = Promise.resolve();
let saveGeneration = 0;
let saveLoading = false;
// The bytes of the write on the wire, for the unload path to leave alone.
let inFlightSave: Uint8Array | null = null;
// Progress the server has not taken yet, kept in the browser with the frame
// from the moment the game wrote it. Stored before every upload attempt, so a
// sync that fails offline retries later with that frame rather than a newer one.
let pendingSave: PendingAsset | null = null;
// One row per session: a save an earlier session never got through still owes
// the server its own version, so this must not write over it.
const pendingSaveId = pendingAssetId(romRef.value.id);
async function rememberPendingSave(
  saveBytes: ArrayBuffer,
  screenshotBytes?: ArrayBuffer,
) {
  pendingSave = {
    id: pendingSaveId,
    kind: "save",
    romId: romRef.value.id,
    romName: romRef.value.name ?? romRef.value.fs_name_no_ext,
    bytes: saveBytes,
    screenshotBytes,
    slot: loadedSave?.slot || props.saveSlot || undefined,
    emulator: window.EJS_core,
    deviceId: deviceIDRef.value,
    capturedAt: Date.now(),
  };
  await pendingAssetStore.write(pendingSave);
}
async function forgetPendingSave() {
  pendingSave = null;
  await pendingAssetStore.clear(pendingSaveId);
}
// The tick re-offers a save whose upload failed on every pass, so what was
// said for these bytes is remembered: every save the game writes is announced,
// every retry of the same one is not.
let heldBackSave: Uint8Array | null = null;
function announceSaveHeldBack(saveFile: Uint8Array) {
  heldBackSave = saveFile;
  displayMessage("Save kept in this browser, it will sync later", {
    duration: 4000,
    tone: "warning",
    icon: "mdi-cloud-clock-outline",
  });
}
function writeSave(
  file: { saveFile: ArrayBuffer; screenshotFile?: ArrayBuffer },
  generation = saveGeneration,
): Promise<SaveSchema | null> {
  if (saveLoading) return Promise.resolve(null);
  const write = saveWrite.then(async () => {
    if (generation !== saveGeneration) return null;
    const bytes = new Uint8Array(file.saveFile);
    inFlightSave = bytes;
    try {
      const save = await saveSave({
        rom: romRef.value,
        save: sessionSaveRef.value,
        deviceId: deviceIDRef.value,
        slot: loadedSave?.slot || props.saveSlot || undefined,
        ...file,
      });
      if (save && generation === saveGeneration) {
        sessionSaveRef.value = save;
        saveTracker.markUploaded(bytes);
      }
      return save;
    } finally {
      inFlightSave = null;
    }
  });
  saveWrite = write.catch(() => null);
  return write;
}
// Forced writes (Save button, Save & Quit) wait for the queue, then skip only
// when no version was opened yet and the SRAM still matches a slotted save
// loaded from the server (a slot-less one still has to reach the slot).
async function writeSaveIfChanged(file: {
  saveFile: ArrayBuffer;
  screenshotFile?: ArrayBuffer;
}): Promise<boolean> {
  const generation = saveGeneration;
  await saveWrite;
  if (
    !sessionSaveRef.value &&
    loadedSave?.slot &&
    saveTracker.isUploaded(new Uint8Array(file.saveFile))
  ) {
    return true;
  }
  return (await writeSave(file, generation)) !== null;
}
// A state restores the machine mid-scene, so every frame the core renders and
// every note it plays on the way there belong to a moment the player did not
// pick. Both are held back until the state has landed.
const applyingState = ref(false);
let restoreVolume: (() => void) | null = null;
function silenceUntilStateApplied() {
  applyingState.value = true;
  const emulator = window.EJS_emulator;
  if (restoreVolume || typeof emulator?.setVolume !== "function") return;
  const { volume, muted } = emulator;
  emulator.setVolume(0);
  restoreVolume = () => {
    // setVolume persists the settings before applying them, so the flag goes
    // back first or the next launch starts muted.
    emulator.muted = muted;
    emulator.setVolume(muted ? 0 : volume);
  };
}
function stateApplied() {
  applyingState.value = false;
  restoreVolume?.();
  restoreVolume = null;
}
const theme = useTheme();
const emitter = inject<Emitter<Events>>("emitter");
const { playing, fullScreen } = storeToRefs(playingStore);
const { selectedLanguage } = storeToRefs(languageStore);

// Declare global variables for EmulatorJS
declare global {
  interface Window {
    EJS_core: string;
    EJS_biosUrl: string;
    EJS_player: string;
    EJS_pathtodata: string;
    EJS_color: string;
    EJS_gameID: number;
    EJS_gameName: string;
    EJS_backgroundImage: string;
    EJS_backgroundColor: string;
    EJS_backgroundBlur: boolean;
    EJS_gameUrl: string;
    EJS_loadStateURL: string | null;
    EJS_cheats: string;
    EJS_gameParentUrl: string;
    EJS_gamePatchUrl: string;
    EJS_netplayServer: string;
    EJS_netplayICEServers: NetplayICEServer[];
    EJS_alignStartButton: "top" | "center" | "bottom";
    EJS_startOnLoaded: boolean;
    EJS_fullscreenOnLoaded: boolean;
    EJS_threads: boolean;
    EJS_controlScheme: string | null;
    EJS_defaultOptions: object;
    EJS_defaultControls: object;
    EJS_emulator: any; // eslint-disable-line @typescript-eslint/no-explicit-any
    EJS_language: string;
    EJS_disableAutoLang: boolean;
    EJS_DEBUG_XX: boolean;
    EJS_CacheLimit: number;
    EJS_Buttons: Record<string, boolean>;
    EJS_VirtualGamepadSettings: Record<string, unknown>;
    EJS_volume: number;
    EJS_paths: Record<string, string>;
    EJS_startButtonName: string;
    EJS_softLoad: boolean;
    EJS_screenCapture: object;
    EJS_externalFiles: Record<string, string>;
    EJS_videoRotation: number;
    EJS_fixedSaveInterval: number;
    EJS_disableCue: boolean;
    EJS_dontExtractRom: boolean;
    EJS_dontExtractBIOS: boolean;
    EJS_disableDatabases: boolean;
    EJS_disableLocalStorage: boolean;
    EJS_disableAutoUnload: boolean;
    EJS_disableBatchBootup: boolean;
    EJS_onGameStart: () => void;
    EJS_onSaveState: (args: {
      screenshot?: ArrayBuffer;
      state: ArrayBuffer;
    }) => void;
    EJS_onLoadState: () => void;
    EJS_onSaveSave: (args: {
      screenshot: ArrayBuffer;
      save: ArrayBuffer;
    }) => void;
    EJS_onLoadSave: () => void;
    // Socket.IO global, bundled by EmulatorJS and used by its netplay code.
    io?: ((url: string, opts?: Record<string, unknown>) => unknown) & {
      __rommNetplayPatched?: boolean;
    };
  }
}

const supportedCores = getSupportedEJSCores(
  romRef.value.platform_slug,
  configStore.config.EJS_NETPLAY_ENABLED,
);
window.EJS_core =
  supportedCores.find((core) => core === props.core) ?? supportedCores[0];
window.EJS_controlScheme = getControlSchemeForPlatform(
  romRef.value.platform_slug,
);
window.EJS_threads = areThreadsRequiredForEJSCore(window.EJS_core);
window.EJS_gameID = romRef.value.id;
invalidateEmulatorJSRomCacheIfRenamed(romRef.value);
window.EJS_gameUrl = getDownloadPath({
  rom: romRef.value,
  fileIDs: props.disc ? [props.disc] : [],
});
window.EJS_biosUrl = props.bios
  ? `/api/firmware/${props.bios.id}/content/${props.bios.file_name}`
  : "";
window.EJS_player = "#game";
window.EJS_color = "#A453FF";
window.EJS_alignStartButton = "center";
window.EJS_startOnLoaded = true;
window.EJS_backgroundImage = `${window.location.origin}/assets/logos/romm_logo_xbox_one_circle_boot.svg`;
window.EJS_backgroundColor = theme.current.value.colors.background;
window.EJS_Buttons = {
  // Disable the standard exit button to implement our own
  exitEmulation: false,
};
const coreOptions = configStore.getEJSCoreOptions(window.EJS_core);
window.EJS_defaultOptions = {
  // Force saving saves and states to the browser
  "save-state-location": "browser",
  rewindEnabled: "enabled",
  ...coreOptions,
};
const ejsControls = configStore.getEJSControls(props.core);
if (ejsControls) window.EJS_defaultControls = ejsControls;
// Set a valid game name
window.EJS_gameName = romRef.value.fs_name_no_tags
  .replace(INVALID_CHARS_REGEX, "")
  .trim();
window.EJS_language = selectedLanguage.value.value.replace("_", "-");
window.EJS_disableAutoLang = true;

const {
  EJS_DEBUG,
  EJS_CACHE_LIMIT,
  EJS_DISABLE_AUTO_UNLOAD,
  EJS_DISABLE_BATCH_BOOTUP,
  EJS_NETPLAY_ICE_SERVERS,
  EJS_NETPLAY_ENABLED,
  EJS_ENABLE_AUTO_SAVE_SYNC,
} = configStore.config;
// Full origin (with scheme)
window.EJS_netplayServer = EJS_NETPLAY_ENABLED ? window.location.origin : "";
window.EJS_netplayICEServers = EJS_NETPLAY_ENABLED
  ? EJS_NETPLAY_ICE_SERVERS
  : [];
window.EJS_DEBUG_XX = EJS_DEBUG;
window.EJS_disableAutoUnload = EJS_DISABLE_AUTO_UNLOAD;
window.EJS_disableBatchBootup = EJS_DISABLE_BATCH_BOOTUP;
if (EJS_CACHE_LIMIT !== null) window.EJS_CacheLimit = EJS_CACHE_LIMIT;

installEJSDefaultOptionsTrap();

onMounted(() => {
  window.scrollTo(0, 0);
  // Registered before EmulatorJS binds its own unload handler, so the
  // pending-save check runs first.
  window.addEventListener("beforeunload", onBeforeUnload);
  window.addEventListener("pagehide", onPageHide);
  if (props.bios) {
    localStorage.setItem(
      `player:${romRef.value.platform_slug}:bios_id`,
      props.bios.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${romRef.value.platform_slug}:bios_id`);
  }

  if (props.core) {
    // Remember the core per-game, and per-platform as the fallback default
    localStorage.setItem(`player:${romRef.value.id}:core`, props.core);
    localStorage.setItem(
      `player:${romRef.value.platform_slug}:core`,
      props.core,
    );
  } else {
    localStorage.removeItem(`player:${romRef.value.id}:core`);
    localStorage.removeItem(`player:${romRef.value.platform_slug}:core`);
  }

  if (props.disc) {
    localStorage.setItem(
      `player:${romRef.value.id}:disc`,
      props.disc.toString(),
    );
  } else {
    localStorage.removeItem(`player:${romRef.value.id}:disc`);
  }

  emitter?.on("saveSelected", loadSave);
  emitter?.on("stateSelected", loadState);
});

onBeforeUnmount(async () => {
  disposed = true;
  window.removeEventListener("beforeunload", onBeforeUnload);
  window.removeEventListener("pagehide", onPageHide);
  uninstallAutoSaveSync();
  emitter?.off("saveSelected", loadSave);
  emitter?.off("stateSelected", loadState);
  exitEmulatorOnce();
  fullScreen.value = false;
  playing.value = false;
});

type MessageTone = "success" | "error" | "warning" | "info";

// The app's own toast host: it stacks, so two notices raised together read as
// two, and it draws its icons as components rather than through a font class.
function displayMessage(
  message: string,
  {
    duration,
    tone = "info",
    icon,
  }: {
    duration: number;
    tone?: MessageTone;
    icon?: string;
  },
) {
  emitter?.emit("snackbarShow", {
    msg: message,
    color: tone,
    icon,
    timeout: duration,
  });
}

// Poll until EmulatorJS' gameManager is ready to accept save/state
// injection. A fixed delay is unreliable: heavier/threaded cores (SNES with
// enhancement chips, N64, DS) need longer than a few ms to boot, and applying
// a state before the core is ready leaves it broken (black screen).
async function waitForGameManager(timeoutMs = 5000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const gameManager = window.EJS_emulator?.gameManager;
    if (gameManager?.FS && gameManager.getSaveFilePath) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

// Settle window around applying a state: cores need a few frames rendered
// before loadState takes cleanly, and RetroArch applies it off its task queue.
const STATE_APPLY_SETTLE_MS = 500;

// Periodic save upload on the "saveSaveFiles" tick that pollSaveFiles fires
// (see createSaveSyncTracker). EmulatorJS has no `off`: the handler stays
// subscribed and this slot is what tells it the component still owns it.
let autoSaveSyncEmulator: object | null = null;
let stopSavePolling: (() => void) | null = null;
// The boot path awaits before installing, so it may land after unmount.
let disposed = false;
function installAutoSaveSync() {
  const emulator = window.EJS_emulator;
  if (disposed || !emulator?.gameManager) return;
  if (autoSaveSyncEmulator === emulator) return;
  autoSaveSyncEmulator = emulator;
  let uploading = false;
  emulator.on("saveSaveFiles", async (saveFile: Uint8Array | null) => {
    if (autoSaveSyncEmulator !== emulator || uploading || !saveFile?.byteLength)
      return;
    if (!saveTracker.shouldUpload(saveFile)) return;
    uploading = true;
    try {
      const saveBytes = toArrayBuffer(saveFile);
      // The capture needs the game running, so it happens on the tick. A retry
      // reuses the frame stored for these bytes instead of taking a new one,
      // which would picture the moment the network came back.
      const screenshotFile =
        storedScreenshotFor(pendingSave, saveBytes) ??
        (await captureScreenshot());
      await rememberPendingSave(saveBytes, screenshotFile);
      const save = await writeSave({ saveFile: saveBytes, screenshotFile });
      if (save) {
        await forgetPendingSave();
        heldBackSave = null;
        romsStore.update(romRef.value);
        displayMessage("Save synced with server", {
          duration: 3000,
          tone: "success",
          icon: "mdi-cloud-sync",
        });
        // A write voided by a save being loaded is not the server refusing it.
      } else if (!saveLoading && !bytesEqual(saveFile, heldBackSave)) {
        announceSaveHeldBack(saveFile);
      }
    } catch (error) {
      console.error("Periodic save sync failed", error);
    } finally {
      uploading = false;
    }
  });
  stopSavePolling = pollSaveFiles(emulator);
}
function uninstallAutoSaveSync() {
  autoSaveSyncEmulator = null;
  stopSavePolling?.();
  stopSavePolling = null;
}
// A save written right before Quit or a back navigation has not had its two
// ticks yet, so leaving the player uploads whatever the server lacks.
async function flushPendingSave() {
  const emulator = window.EJS_emulator;
  if (!autoSaveSyncEmulator || autoSaveSyncEmulator !== emulator) return;
  uninstallAutoSaveSync();
  emulator.pause();
  await new Promise((resolve) => setTimeout(resolve, 50));
  const saveFile: Uint8Array | null = emulator.gameManager.getSaveFile();
  if (!saveFile?.byteLength || !saveTracker.hasChanges(saveFile)) return;
  const saveBytes = toArrayBuffer(saveFile);
  // The exit takes no frame of its own; it carries the one stored when the
  // game wrote these bytes, if a sync got that far.
  const screenshotFile = storedScreenshotFor(pendingSave, saveBytes);
  await rememberPendingSave(saveBytes, screenshotFile);
  try {
    if (await writeSave({ saveFile: saveBytes, screenshotFile })) {
      await forgetPendingSave();
      romsStore.update(romRef.value);
    }
  } catch (error) {
    console.error("Save sync on exit failed", error);
  }
}
onBeforeRouteLeave(flushPendingSave);
// A v2 shell that leaves by replacing the document aborts the navigation, so
// the guard above never runs and the flush has to be asked for. Idempotent.
defineExpose({ flushPendingSave });
// Closing the tab cancels requests in flight, so a save the tick has not
// uploaded goes out on `pagehide` with fetch keepalive, which the browser caps
// at 64 KB. `beforeunload` asks first while one is pending: for a bigger save
// that prompt is the only way to keep it.
let unloadSave: Uint8Array | null = null;
function onBeforeUnload(event: BeforeUnloadEvent) {
  // A close cancelled earlier leaves the bytes it captured behind.
  unloadSave = null;
  const emulator = window.EJS_emulator;
  if (!autoSaveSyncEmulator || autoSaveSyncEmulator !== emulator) return;
  if (saveLoading) return;
  const saveFile: Uint8Array | null = emulator.gameManager.getSaveFile();
  if (!saveFile?.byteLength || !saveTracker.hasChanges(saveFile)) return;
  unloadSave = saveFile;
  // EmulatorJS tears the core down on this event, and a cancelled close has
  // to keep the game running.
  event.stopImmediatePropagation();
  // preventDefault covers the current spec, returnValue the older browsers.
  event.preventDefault();
  event.returnValue = "";
}
function onPageHide() {
  if (!unloadSave || !saveTracker.hasChanges(unloadSave)) return;
  // These bytes are already on the wire: a second POST would only open a
  // duplicate version.
  if (inFlightSave && bytesEqual(inFlightSave, unloadSave)) return;
  saveSaveOnUnload({
    rom: romRef.value,
    save: sessionSaveRef.value,
    saveFile: toArrayBuffer(unloadSave),
    deviceId: deviceIDRef.value,
    slot: loadedSave?.slot || props.saveSlot || undefined,
  });
}

// Saves management
async function loadSave(save: SaveSchema) {
  saveGeneration += 1;
  saveLoading = true;
  loadedSave = save;
  sessionSaveRef.value = null;

  try {
    const { data } = await api.get(save.download_path.replace("/api", ""), {
      responseType: "arraybuffer",
      params: { device_id: deviceIDRef.value },
    });
    if (data) {
      const bytes = new Uint8Array(data);
      loadEmulatorJSSave(bytes);
      saveTracker.seed(bytes);
      displayMessage("Save loaded from server", {
        duration: 3000,
        icon: "mdi-cloud-download-outline",
      });
      return;
    }

    const file = await window.EJS_emulator.selectFile();
    loadEmulatorJSSave(new Uint8Array(await file.arrayBuffer()));
  } finally {
    saveLoading = false;
  }
}

window.EJS_onLoadSave = async function () {
  window.EJS_emulator.pause();
  window.EJS_emulator.toggleFullscreen(false);
  emitter?.emit("selectSaveDialog", romRef.value);
};

window.EJS_onSaveSave = async function ({
  save: saveFile,
  screenshot: emulatorScreenshot,
}) {
  const screenshotFile = await resolveScreenshot(emulatorScreenshot);
  const synced = await writeSaveIfChanged({ saveFile, screenshotFile });

  romsStore.update(romRef.value);

  if (synced) {
    heldBackSave = null;
    displayMessage("Save synced with server", {
      duration: 4000,
      tone: "success",
      icon: "mdi-cloud-sync",
    });
  } else {
    // Asked for by hand, so it answers every time, and the tick behind it
    // knows these bytes have been spoken for.
    announceSaveHeldBack(new Uint8Array(saveFile));
  }
};

// States management
// A state restores the SRAM along with the rest of the machine, so the bytes
// the tick reads next belong to the state, not to progress the player made.
async function rebaselineAfterState() {
  await new Promise((resolve) => setTimeout(resolve, STATE_APPLY_SETTLE_MS));
  baselineSaveTrackerFromEmulator();
}

async function loadState(state: StateSchema) {
  silenceUntilStateApplied();
  try {
    const { data } = await api.get(state.download_path.replace("/api", ""), {
      responseType: "arraybuffer",
    });
    if (data) {
      loadEmulatorJSState(new Uint8Array(data));
      displayMessage("State loaded from server", {
        duration: 3000,
        icon: "mdi-cloud-download-outline",
      });
      await rebaselineAfterState();
      return;
    }

    const file = await window.EJS_emulator.selectFile();
    loadEmulatorJSState(new Uint8Array(await file.arrayBuffer()));
    await rebaselineAfterState();
  } finally {
    stateApplied();
  }
}

window.EJS_onLoadState = async function () {
  window.EJS_emulator.pause();
  window.EJS_emulator.toggleFullscreen(false);
  emitter?.emit("selectStateDialog", romRef.value);
};

window.EJS_onSaveState = async function ({
  state: stateFile,
  screenshot: emulatorScreenshot,
}) {
  const screenshotFile = await resolveScreenshot(emulatorScreenshot);
  const state = await saveState({
    rom: romRef.value,
    stateFile,
    screenshotFile,
  });
  window.EJS_emulator.storage.states.put(
    window.EJS_emulator.getBaseFileName() + ".state",
    stateFile,
  );

  romsStore.update(romRef.value);

  if (state) {
    displayMessage("State synced with server", {
      duration: 4000,
      tone: "success",
      icon: "mdi-cloud-sync",
    });
  } else {
    displayMessage("State kept in this browser, it will sync later", {
      duration: 4000,
      tone: "warning",
      icon: "mdi-cloud-clock-outline",
    });
  }
};

window.EJS_onGameStart = async () => {
  // EmulatorJS' own notices (its browser save-state slots) go through the
  // same host, so nothing of ours is overwritten by one of theirs.
  const emulator = window.EJS_emulator;
  if (emulator && !emulator.__rommMessageStack) {
    emulator.__rommMessageStack = true;
    emulator.displayMessage = (text: string, duration?: number) =>
      displayMessage(text, { duration: duration ?? 3000 });
  }

  if (props.state) silenceUntilStateApplied();
  // The emulator now owns the keyboard: every key, "/" included, belongs to
  // the game (a DOS prompt typing "mount A / -t floppy" must not reach the
  // global hotkeys). Callers flag this at launch too, but taking it from the
  // emulator's own start hook keeps the flag true for any entry point.
  playing.value = true;

  // Install netplay overrides synchronously, before any await below, so they
  // are in place before room polling or a Create/Join action can start.
  const netplay = window.EJS_emulator?.netplay;
  if (netplay) {
    // EmulatorJS only prompts for a player name when netplay.name is unset,
    // so presetting it adopts the RomM account username automatically.
    if (!netplay.name && authStore.user?.username) {
      netplay.name = authStore.user.username;
    }
    netplay.getOpenRooms = async () => {
      try {
        const response = await fetch(
          `/api/netplay/list?game_id=${window.EJS_gameID}`,
        );
        if (!response.ok) return {};
        return await response.json();
      } catch (error) {
        console.error("Error fetching netplay rooms:", error);
        return {};
      }
    };
  }

  // Wrap the bundled global `io` so netplay uses mounted socket path.
  if (window.io && !window.io.__rommNetplayPatched) {
    const originalIo = window.io;
    const patchedIo = ((url: string, opts?: Record<string, unknown>) =>
      originalIo(url, {
        ...opts,
        path: "/netplay/socket.io",
      })) as NonNullable<Window["io"]>;
    patchedIo.__rommNetplayPatched = true;
    window.io = patchedIo;
  }

  void (async () => {
    const ready = await waitForGameManager();
    if (!ready) {
      console.warn("Game manager not ready for save/state injection");
      stateApplied();
    } else {
      // A state restores the whole machine, SRAM included, so a save applied
      // alongside it would be discarded: the state wins when both are set.
      if (props.state) {
        await new Promise((resolve) =>
          setTimeout(resolve, STATE_APPLY_SETTLE_MS),
        );
        await loadState(props.state);
      } else if (props.save) {
        await loadSave(props.save);
      } else {
        baselineSaveTrackerFromEmulator();
      }
      if (EJS_ENABLE_AUTO_SAVE_SYNC) {
        try {
          installAutoSaveSync();
        } catch (error) {
          console.error("Failed to enable periodic save sync", error);
        }
      }
    }

    if (window.EJS_emulator) {
      window.EJS_emulator.settings = {
        ...window.EJS_emulator.settings,
        "save-state-location": "browser",
      };
    }
  })();

  const quickLoad = createQuickLoadButton();
  quickLoad.addEventListener("click", () => {
    if (
      window.EJS_emulator.settings["save-state-location"] === "browser" &&
      window.EJS_emulator.saveInBrowserSupported()
    ) {
      window.EJS_emulator.storage.states
        .get(window.EJS_emulator.getBaseFileName() + ".state")
        .then(async (e: Uint8Array) => {
          loadEmulatorJSState(e);
          displayMessage("Quick load from server", {
            duration: 3000,
            icon: "mdi-flash",
          });
          await rebaselineAfterState();
        });
    }
  });

  const exitEmulation = createExitEmulationButton();
  exitEmulation.addEventListener("click", async () => {
    if (!romRef.value || !window.EJS_emulator) return immediateExit();
    await flushPendingSave();
    romsStore.update(romRef.value);
    immediateExit();
  });

  const saveAndQuit = createSaveQuitButton();
  saveAndQuit.addEventListener("click", async () => {
    uninstallAutoSaveSync();
    if (!romRef.value || !window.EJS_emulator) return immediateExit();

    // Grab the state's screenshot while the game is still running (EmulatorJS
    // reads the live canvas), then pause before serializing state/save.
    // Reading state from a running threaded core (SNES, N64) races the worker
    // thread and yields torn buffers, producing corrupt states.
    const screenshotFile = await captureScreenshot();
    window.EJS_emulator.pause();
    await new Promise((resolve) => setTimeout(resolve, 50));

    const stateFile = window.EJS_emulator.gameManager.getState();
    const saveFile = window.EJS_emulator.gameManager.getSaveFile();

    // The state and the save go to different endpoints, so upload both at
    // once. The save carries no picture here: an in-game save gets its own
    // when the sync tick uploads it.
    await Promise.all([
      saveState({ rom: romRef.value, stateFile, screenshotFile }),
      writeSaveIfChanged({ saveFile }),
    ]);

    romsStore.update(romRef.value);
    immediateExit();
  });
};

function immediateExit() {
  // Play-session recording is owned by the v2 player shell (usePlaySession);
  // this only returns to the game details view.
  router
    .push({ name: ROUTES.ROM, params: { rom: romRef.value.id } })
    .catch((error) => {
      console.error("Error navigating to console rom", error);
    });
}

onUnmounted(() => {
  // Force full reload to reset COEP/COOP, so cross-origin isolation is turned off.
  window.location.reload();
});
</script>

<template>
  <div id="game" />
  <div v-if="applyingState" class="ejs-state-cover" aria-hidden="true" />
  <div
    v-if="rom.ss_metadata?.bezel_path"
    class="pointer-events-none fixed inset-0 flex items-center justify-center z-20 overflow-hidden"
    aria-hidden="true"
  >
    <img
      :src="rom.ss_metadata.bezel_path"
      alt=""
      class="select-none"
      draggable="false"
      style="height: 100vh; max-height: 100%; width: auto; object-fit: cover"
    />
  </div>
</template>

<style>
/* Up until a state has been applied: the core has to render frames for the
   load to take, and they picture a scene the player did not ask for. */
.ejs-state-cover {
  position: fixed;
  inset: 0;
  z-index: 30;
  pointer-events: none;
  background: black;
}

#game .ejs_cheat_code {
  background-color: white;
}

#game .ejs_settings_transition {
  height: fit-content;
}

#game .ejs_game_background {
  background-size: 40%;
}

/* Hide the exit button */
#game .ejs_menu_bar .ejs_menu_button:nth-child(-1) {
  display: none;
}
</style>
