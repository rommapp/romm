<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import {
  computed,
  onMounted,
  onBeforeUnmount,
  ref,
  watch,
  nextTick,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type { DetailedRomSchema } from "@/__generated__/models/DetailedRomSchema";
import NavigationText from "@/console/components/NavigationText.vue";
import { useInputScope } from "@/console/composables/useInputScope";
import { useThemeAssets } from "@/console/composables/useThemeAssets";
import { ROUTES } from "@/plugins/router";
import api from "@/services/api";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeConfig from "@/stores/config";
import storeLanguage from "@/stores/language";
import {
  getSupportedEJSCores,
  getControlSchemeForPlatform,
  areThreadsRequiredForEJSCore,
  getDownloadPath,
} from "@/utils";

const { t } = useI18n();
const createPlayerStorage = (romId: number, platformSlug: string) => ({
  initialSaveId: useLocalStorage(
    `player:${romId}:initial_save_id`,
    null as string | null,
  ),
  initialStateId: useLocalStorage(
    `player:${romId}:initial_state_id`,
    null as string | null,
  ),
  disc: useLocalStorage(`player:${romId}:disc`, null as string | null),
  core: useLocalStorage(`player:${platformSlug}:core`, null as string | null),
  biosId: useLocalStorage(
    `player:${platformSlug}:bios_id`,
    null as string | null,
  ),
});

const route = useRoute();
const router = useRouter();
const { getBezelImagePath } = useThemeAssets();
const configStore = storeConfig();
const languageStore = storeLanguage();
const { selectedLanguage } = storeToRefs(languageStore);
const romId = Number(route.params.rom);
const initialSaveId = route.query.save ? Number(route.query.save) : null;
const initialStateId = route.query.state ? Number(route.query.state) : null;
const romRef = ref<DetailedRomSchema | null>(null);
const showHint = ref(true);
const bezelSrc = ref<string>("");
const showExitPrompt = ref(false);
const savingState = ref(false);
const saveError = ref("");
const focusedExitIndex = ref(0);
const loaderError = ref("");
const loaderStatus = ref<
  "idle" | "loading-local" | "loading-cdn" | "loaded" | "failed"
>("idle");

let pausedByPrompt = false;

const exitOptions = computed(() => [
  {
    id: "save",
    label: "console.game-exit-save",
    desc: "console.game-exit-save-desc",
  },
  {
    id: "nosave",
    label: "console.game-exit-nosave",
    desc: "console.game-exit-nosave-desc",
  },
  {
    id: "cancel",
    label: "console.game-exit-cancel",
    desc: "console.game-exit-cancel-desc",
  },
]);

const { subscribe } = useInputScope();
let exitScopeOff: (() => void) | null = null;
let requestedAnimationFrame: number | null = null;
let lastPressedKeys: Record<number, number> = { 8: 0, 9: 0 };

const INVALID_CHARS_REGEX = /[#<$+%>!`&*'|{}/\\?"=@:^\r\n]/gi;

function immediateExit() {
  router
    .push({ name: ROUTES.CONSOLE_ROM, params: { rom: romId } })
    .catch((error) => {
      console.error("Error navigating to console rom", error);
    });
}

function showPrompt() {
  if (showExitPrompt.value) return; // Prompt already open
  showExitPrompt.value = true;
  saveError.value = "";
  focusedExitIndex.value = 0;

  window.EJS_emulator.pause();
  pausedByPrompt = true;

  nextTick(() => {
    exitScopeOff?.();
    exitScopeOff = subscribe(handleExitAction);
  });
}

function handleExitAction(action: string) {
  if (!showExitPrompt.value) return false;
  if (action === "moveUp") {
    moveExitFocus(-1);
    return true;
  }
  if (action === "moveDown") {
    moveExitFocus(1);
    return true;
  }
  if (action === "confirm") {
    activateExitOption(exitOptions.value[focusedExitIndex.value].id);
    return true;
  }
  if (action === "back") {
    cancelExit();
    return true;
  }
  return false;
}

async function saveAndExit() {
  if (savingState.value) return;
  savingState.value = true;

  try {
    // CRITICAL: The game must be RUNNING for screenshot to work!
    // We paused it in showPrompt(), so we need to resume it first
    console.info(
      "Resuming game before screenshot (emujs expects running game)",
    );
    if (window.EJS_emulator.paused) {
      window.EJS_emulator.play();
      // Wait a moment for the game to fully resume
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    const screenshotFile = await window.EJS_emulator.gameManager.screenshot();
    const stateFile = window.EJS_emulator.gameManager.getState();

    // Upload using original saveState utility
    await uploadState(stateFile, screenshotFile);

    // Clean exit
    immediateExit();
  } catch (error) {
    saveError.value = `Save failed: ${error}`;
  } finally {
    savingState.value = false;
  }
}

async function uploadState(
  stateFile: ArrayBuffer,
  screenshotFile: ArrayBuffer,
) {
  if (!romRef.value) return;
  const filename = `${romRef.value.fs_name_no_ext.trim()} [${new Date()
    .toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", " ")
    .replace("Z", "")}]`;

  try {
    const stateApi = await import("@/services/api/state");

    const uploadedStates = await stateApi.default.uploadStates({
      rom: romRef.value,
      emulator: window.EJS_core,
      statesToUpload: [
        {
          stateFile: new File([stateFile], `${filename}.state`, {
            type: "application/octet-stream",
          }),
          screenshotFile: new File([screenshotFile], `${filename}.png`, {
            type: "application/octet-stream",
          }),
        },
      ],
    });

    const uploadedState = uploadedStates[0];
    if (uploadedState.status == "fulfilled") {
      if (romRef.value) romRef.value.user_states.unshift(uploadedState.value);
      return uploadedState.value;
    } else {
      throw new Error("State upload was rejected");
    }
  } catch (error) {
    console.error("stateApi upload failed:", error);
    throw error;
  }
}

function cancelExit() {
  showExitPrompt.value = false;
  if (pausedByPrompt) {
    window.EJS_emulator.play();
    pausedByPrompt = false;
  }

  // Reset combo detection timestamps so start+select works again right away
  lastPressedKeys[8] = 0;
  lastPressedKeys[9] = 0;
  exitScopeOff?.();
  exitScopeOff = null;
}

function activateExitOption(id: string) {
  // Block other actions while saving
  if (savingState.value && id !== "save") return;

  if (id === "save") {
    saveAndExit();
  } else if (id === "nosave") {
    immediateExit();
  } else {
    cancelExit();
  }
}

function moveExitFocus(delta: number) {
  const total = exitOptions.value.length;
  focusedExitIndex.value = (focusedExitIndex.value + delta + total) % total;
}

function attachKeyboardExit() {
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      showPrompt();
    }
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}

function attachGamepadExit(options?: { windowMs?: number }) {
  const EXIT_WINDOW_MS = options?.windowMs ?? 200;
  const BTN = { A: 0, B: 1, SELECT: 8, START: 9, UP: 12, DOWN: 13 } as const;

  // Per-pad state so we don't combine the input from other pads
  interface PadState {
    prev: boolean[];
    lastEdge: Record<number, number>;
  }
  const padState: Record<number, PadState> = {};

  let running = true;

  const loop = () => {
    const pads = navigator.getGamepads?.() || [];
    const now = performance.now();

    for (const pad of pads) {
      if (!pad) continue;
      const st = (padState[pad.index] ??= {
        prev: new Array(pad.buttons.length).fill(false),
        lastEdge: {},
      });

      const pressed = (i: number) => !!pad.buttons[i]?.pressed;
      const edge = (i: number) => pressed(i) && !st.prev[i];

      // Exit combo detection (start + select)
      if (!showExitPrompt.value) {
        let combo = false;

        // If either Start or Select edges, stamp its edge time
        if (edge(BTN.SELECT)) {
          st.lastEdge[BTN.SELECT] = now;
          const tOther = st.lastEdge[BTN.START] ?? -Infinity;
          if (now - tOther <= EXIT_WINDOW_MS) combo = true;
        }
        if (edge(BTN.START)) {
          st.lastEdge[BTN.START] = now;
          const tOther = st.lastEdge[BTN.SELECT] ?? -Infinity;
          if (now - tOther <= EXIT_WINDOW_MS) combo = true;
        }

        if (combo) {
          showPrompt();
        }
      } else {
        if (edge(BTN.A))
          activateExitOption(exitOptions.value[focusedExitIndex.value].id);
        if (edge(BTN.B)) cancelExit();
      }
      for (let i = 0; i < pad.buttons.length; i++) {
        st.prev[i] = !!pad.buttons[i]?.pressed;
      }
    }
    if (running) {
      requestedAnimationFrame = requestAnimationFrame(loop);
    }
  };

  requestedAnimationFrame = requestAnimationFrame(loop);

  return () => {
    running = false;
    if (requestedAnimationFrame != null) {
      cancelAnimationFrame(requestedAnimationFrame);
      requestedAnimationFrame = null;
    }
  };
}

watch(showExitPrompt, (v) => {
  if (!v) {
    exitScopeOff?.();
    exitScopeOff = null;
  }
});

async function boot() {
  // Fetch rom details
  const { data: rom } = await romApi.getRom({ romId });
  romRef.value = rom;

  // Create player storage instances
  const playerStorage = createPlayerStorage(rom.id, rom.platform_slug);

  const selectedInitialSave = initialSaveId
    ? rom.user_saves?.find((s) => s.id === initialSaveId)
    : null;

  const selectedInitialState = initialStateId
    ? rom.user_states?.find((s) => s.id === initialStateId)
    : null;

  document.title = `${rom.name} | Play`;
  bezelSrc.value =
    rom.ss_metadata?.bezel_path || getBezelImagePath(rom.platform_slug).value;

  // Configure EmulatorJS globals
  const supported = getSupportedEJSCores(rom.platform_slug);
  const core =
    playerStorage.core.value && supported.includes(playerStorage.core.value)
      ? playerStorage.core.value
      : supported[0];

  window.EJS_core = core;
  window.EJS_controlScheme = getControlSchemeForPlatform(rom.platform_slug);
  window.EJS_threads = areThreadsRequiredForEJSCore(core);
  window.EJS_gameID = rom.id;

  if (initialSaveId) {
    // Persist chosen save ID for later logic
    playerStorage.initialSaveId.value = String(initialSaveId);
  }
  if (initialStateId) {
    playerStorage.initialStateId.value = String(initialStateId);
  }

  // Disc selection persistence
  const discId = playerStorage.disc.value
    ? parseInt(playerStorage.disc.value)
    : null;
  window.EJS_gameUrl = getDownloadPath({
    rom: rom,
    fileIDs: discId ? [discId] : [],
  });

  // BIOS selection persistence
  try {
    const { data: firmware } = await firmwareApi.getFirmware({
      platformId: rom.platform_id,
    });
    const bios = playerStorage.biosId.value
      ? firmware.find((f) => f.id === parseInt(playerStorage.biosId.value!))
      : null;

    window.EJS_biosUrl = bios
      ? `/api/firmware/${bios.id}/content/${bios.file_name}`
      : "";
  } catch {
    window.EJS_biosUrl = "";
  }

  window.EJS_player = "#game";
  window.EJS_Buttons = {
    playPause: false,
    restart: false,
    mute: false,
    settings: false,
    fullscreen: false,
    saveState: false,
    loadState: false,
    screenRecord: false,
    gamepad: false,
    cheat: false,
    volume: false,
    saveSavFiles: false,
    loadSavFiles: false,
    quickSave: false,
    quickLoad: false,
    screenshot: false,
    cacheManager: false,
    exitEmulation: false,
  };
  window.EJS_color = "#A453FF";
  window.EJS_alignStartButton = "center";
  window.EJS_startOnLoaded = true;
  //   window.EJS_fullscreenOnLoaded = true;
  window.EJS_backgroundImage = `${window.location.origin}/assets/logos/romm_logo_xbox_one_circle_boot.svg`;
  window.EJS_backgroundColor = "#000000"; // Match original which uses theme colors, but #000000 should work fine
  const coreOptions = configStore.getEJSCoreOptions(core);
  window.EJS_defaultOptions = {
    "save-state-location": "browser",
    rewindEnabled: "enabled",
    ...coreOptions,
  };
  const ejsControls = configStore.getEJSControls(core);
  if (ejsControls) window.EJS_defaultControls = ejsControls;
  window.EJS_language = selectedLanguage.value.value.replace("_", "-");
  window.EJS_disableAutoLang = true;

  const { EJS_DEBUG, EJS_CACHE_LIMIT } = configStore.config;
  if (EJS_CACHE_LIMIT !== null) window.EJS_CacheLimit = EJS_CACHE_LIMIT;
  window.EJS_DEBUG_XX = EJS_DEBUG;

  // Set a valid game name (affects per-game settings keys)
  window.EJS_gameName = rom.fs_name_no_tags
    .replace(INVALID_CHARS_REGEX, "")
    .trim();

  // Set up EmulatorJS callbacks
  window.EJS_onSaveState = async function ({
    state: stateFile,
    screenshot: screenshotFile,
  }: {
    state: ArrayBuffer;
    screenshot: ArrayBuffer;
  }) {
    try {
      const formData = new FormData();
      formData.append("stateFile", new Blob([stateFile]), "state.save");
      formData.append(
        "screenshotFile",
        new Blob([screenshotFile], { type: "image/png" }),
        "screenshot.png",
      );

      await api.post("/states", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        params: {
          rom_id: rom.id,
          emulator: "emulatorjs",
        },
      });
    } catch (err) {
      console.error("EJS_onSaveState callback failed:", err);
    }
  };

  window.EJS_onSaveSave = async function ({
    save: saveFile,
    screenshot: screenshotFile,
  }: {
    save: ArrayBuffer;
    screenshot: ArrayBuffer;
  }) {
    console.info(
      "EJS_onSaveSave callback triggered",
      "saveFile:",
      saveFile?.byteLength,
      "screenshotFile:",
      screenshotFile?.byteLength,
    );

    try {
      // If I decide to handle save files later, I will implement it here
      console.info("Save file callback executed");
    } catch (err) {
      console.error("EJS_onSaveSave callback failed:", err);
    }
  };

  window.EJS_onLoadState = async function () {
    console.info("[ConsolePlay] EJS_onLoadState callback triggered");
    // State loading UI would go here if needed
  };

  window.EJS_onLoadSave = async function () {
    console.info("[ConsolePlay] EJS_onLoadSave callback triggered");
    // Save loading UI would go here if needed
  };

  // Ensure a controller is auto-assigned to Player 1 when available
  window.EJS_onGameStart = () => {
    if (!window.EJS_emulator) return;
    const waitForGameManager = async () => {
      const deadline = Date.now() + 5000; // 5s timeout
      while (Date.now() < deadline) {
        if (
          window.EJS_emulator.gameManager?.FS &&
          window.EJS_emulator.gameManager.getSaveFilePath
        ) {
          return true;
        }
        await new Promise((r) => setTimeout(r, 100));
      }
      return false;
    };
    const assignFirstPad = () => {
      if (!window.EJS_emulator.gamepad) return;
      if (!Array.isArray(window.EJS_emulator.gamepadSelection))
        window.EJS_emulator.gamepadSelection = ["", "", "", ""];
      if (
        !window.EJS_emulator.gamepad.gamepads ||
        window.EJS_emulator.gamepad.gamepads.length === 0
      )
        return;
      if (!window.EJS_emulator.gamepadSelection[0]) {
        const gp = window.EJS_emulator.gamepad.gamepads[0];
        if (gp) {
          window.EJS_emulator.gamepadSelection[0] = `${gp.id}_${gp.index}`;
          window.EJS_emulator.updateGamepadLabels?.();
        }
      }
    };

    // Assign immediately if a pad exists
    assignFirstPad();

    // Also assign on future connections
    window.EJS_emulator.gamepad?.on?.("connected", assignFirstPad);

    (async () => {
      const ready = await waitForGameManager();
      if (!ready) {
        console.warn("Game manager not ready for save/state injection");
        return;
      }
      const gameManager = window.EJS_emulator.gameManager;
      // Load SAVE (battery / SRAM) if provided
      if (selectedInitialSave?.download_path) {
        try {
          const resp = await fetch(selectedInitialSave.download_path);
          if (!resp.ok) throw new Error("Failed to fetch save");
          const buf = new Uint8Array(await resp.arrayBuffer());
          try {
            const FS = gameManager.FS;
            const path = gameManager.getSaveFilePath();
            // Ensure dirs
            const segs = path.split("/");
            let accum = "";
            for (let i = 0; i < segs.length - 1; i++) {
              if (!segs[i]) continue;
              accum += "/" + segs[i];
              if (!FS.analyzePath(accum).exists) FS.mkdir(accum);
            }
            if (FS.analyzePath(path).exists) FS.unlink(path);
            FS.writeFile(path, buf);
            gameManager.loadSaveFiles?.();
            console.info("[ConsolePlay] Loaded server save into path", path);
          } catch (err) {
            console.warn("[ConsolePlay] Failed writing save file", err);
          }
        } catch (err) {
          console.warn("[ConsolePlay] Save download failed", err);
        }
      }

      // Load STATE if provided (fast-forward once core running)
      if (selectedInitialState?.download_path) {
        try {
          const resp = await fetch(selectedInitialState.download_path);
          if (!resp.ok) throw new Error("Failed to fetch state");
          const buf = new Uint8Array(await resp.arrayBuffer());
          // Some cores need a couple frames; delay slightly
          setTimeout(() => {
            try {
              gameManager.loadState?.(buf);
              console.info("[ConsolePlay] Applied server state");
            } catch (err) {
              console.warn("[ConsolePlay] Applying state failed", err);
            }
          }, 500);
        } catch (err) {
          console.warn("[ConsolePlay] State download failed", err);
        }
      }
    })();
  };

  // Allow route transition animation to settle
  await new Promise((r) => setTimeout(r, 50));

  const EMULATORJS_VERSION = "4.2.3";
  const LOCAL_PATH = "/assets/emulatorjs/data/";
  const CDN_PATH = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data/`;

  function loadScript(src: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Failed loading " + src));
      document.body.appendChild(s);
    });
  }

  async function attemptLoad(path: string, label: "local" | "cdn") {
    loaderStatus.value = label === "local" ? "loading-local" : "loading-cdn";
    window.EJS_pathtodata = path;
    await loadScript(`${path}loader.js`);
  }

  try {
    try {
      await attemptLoad(LOCAL_PATH, "local");
    } catch (e) {
      console.warn("[Play] Local loader failed, trying CDN", e);
      await attemptLoad(CDN_PATH, "cdn");
    }
    // Wait for emulator bootstrap
    const startDeadline = Date.now() + 8000; // 8s
    while (!window.EJS_emulator && Date.now() < startDeadline) {
      await new Promise((r) => setTimeout(r, 100));
    }
    if (!window.EJS_emulator) {
      throw new Error("Emulator did not initialize (EJS_emulator missing)");
    }
    loaderStatus.value = "loaded";
  } catch (err) {
    loaderStatus.value = "failed";
    loaderError.value = (err as Error).message || "Failed to load emulator";
    console.error("[Play] Emulator load failure:", err);
  }

  // Hide the hint after a short delay
  setTimeout(() => {
    showHint.value = false;
  }, 3500);
}

let detachKey: (() => void) | null = null;
let detachPad: (() => void) | null = null;
let booted = false;

onMounted(async () => {
  // Guard against duplicate mounts
  if (booted) return;

  booted = true;
  await boot();
  detachKey = attachKeyboardExit();
  detachPad = attachGamepadExit();
});

onBeforeUnmount(() => {
  window.EJS_emulator?.callEvent?.("exit");
  detachKey?.();
  detachPad?.();
});
</script>

<template>
  <div
    class="play-root fixed inset-0 bg-black text-white z-[70] overflow-hidden"
  >
    <div id="game" class="w-full h-full" />
    <div
      v-if="bezelSrc"
      class="pointer-events-none fixed inset-0 flex items-center justify-center z-20 overflow-hidden"
      aria-hidden="true"
    >
      <img
        :src="bezelSrc"
        alt=""
        class="select-none"
        draggable="false"
        style="height: 100vh; max-height: 100vh; width: auto; object-fit: cover"
      />
    </div>
    <div
      v-if="loaderStatus !== 'loaded'"
      class="absolute inset-0 flex items-center justify-center pointer-events-none"
    >
      <div
        :style="{
          backgroundColor: 'var(--console-play-hint-bg)',
          borderColor: 'var(--console-play-hint-border)',
          color: 'var(--console-play-hint-text)',
        }"
        class="text-center text-sm px-4 py-3 rounded border backdrop-blur"
      >
        <template
          v-if="loaderStatus === 'idle' || loaderStatus === 'loading-local'"
        >
          {{ t("console.emulator-loading") }}
        </template>
        <template v-else-if="loaderStatus === 'loading-cdn'">
          {{ t("console.emulator-cdn") }}
        </template>
        <template v-else-if="loaderStatus === 'failed'">
          <div class="text-red-300 font-medium">
            {{ t("console.emulator-failed") }}
          </div>
          <div class="mt-1 text-[11px] max-w-xs leading-snug break-words">
            {{ loaderError }}
          </div>
        </template>
      </div>
    </div>
    <div
      v-if="showHint"
      :style="{
        backgroundColor: 'var(--console-play-hint-bg)',
        borderColor: 'var(--console-play-hint-border)',
        color: 'var(--console-play-hint-text)',
      }"
      class="absolute top-3 left-1/2 -translate-x-1/2 backdrop-blur px-3 py-1 rounded text-xs border"
    >
      {{ t("console.exit-game") }}
    </div>

    <!-- Exit Prompt Modal -->
    <div
      v-if="showExitPrompt"
      class="absolute inset-0 z-50 flex items-center justify-center"
    >
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        :style="{
          backgroundColor: 'var(--console-modal-bg)',
          borderColor: 'var(--console-modal-border)',
          boxShadow: 'var(--console-modal-shadow)',
        }"
        class="relative w-full max-w-[560px] mx-auto rounded-2xl pa-10 md:p-9 flex flex-col gap-6 focus:outline-none border"
      >
        <div class="flex items-center justify-between">
          <h2
            :style="{ color: 'var(--console-modal-text)' }"
            class="text-xl font-bold tracking-wide drop-shadow"
          >
            {{ t("console.game-exit") }}
          </h2>
          <button
            :disabled="savingState"
            :style="{ color: 'var(--console-modal-text-secondary)' }"
            class="opacity-50 hover:opacity-100 transition-opacity text-lg"
            @click="cancelExit()"
          >
            ✕
          </button>
        </div>
        <div class="flex flex-col gap-3">
          <div
            v-for="(opt, i) in exitOptions"
            :key="opt.id"
            class="group relative rounded-lg px-4 py-3 border transition-all cursor-pointer select-none"
            :class="[
              savingState && opt.id !== 'save'
                ? 'opacity-40 cursor-not-allowed'
                : '',
              focusedExitIndex === i
                ? 'shadow-[0_0_0_2px_var(--console-modal-tile-selected-border),_0_0_18px_-4px_var(--console-modal-tile-selected-border)]'
                : '',
            ]"
            :style="
              focusedExitIndex === i
                ? {
                    borderColor: 'var(--console-modal-tile-selected-border)',
                    backgroundColor: 'var(--console-modal-tile-selected-bg)',
                  }
                : {
                    borderColor: 'var(--console-modal-tile-selected-border)',
                    backgroundColor: 'var(--console-modal-tile-bg)',
                  }
            "
            role="button"
            :aria-selected="focusedExitIndex === i"
            @click="activateExitOption(opt.id)"
            @keydown.enter="activateExitOption(opt.id)"
          >
            <div class="flex items-center gap-3">
              <div class="flex-1">
                <div
                  :style="{
                    color:
                      focusedExitIndex === i
                        ? 'var(--console-modal-text)'
                        : 'var(--console-modal-text-secondary)',
                  }"
                  class="font-semibold text-sm tracking-wide"
                >
                  {{ t(opt.label) }}
                  <span
                    v-if="opt.id === 'save' && savingState"
                    :style="{ color: 'var(--console-play-save-status-text)' }"
                    class="ml-2 text-[10px] font-medium tracking-wide animate-pulse"
                  >
                    {{ t("console.game-saving") }}
                  </span>
                </div>
                <div
                  v-if="opt.desc"
                  :style="{ color: 'var(--console-modal-text-secondary)' }"
                  class="text-xs mt-0.5 opacity-50"
                >
                  {{ t(opt.desc) }}
                </div>
              </div>
              <div
                v-if="focusedExitIndex === i"
                :style="{ color: 'var(--console-play-save-status-text)' }"
                class="text-xs font-medium tracking-wider"
              >
                {{ savingState && opt.id === "save" ? "SAVING" : "" }}
              </div>
            </div>
          </div>
        </div>
        <p v-if="saveError" class="text-xs text-red-400 font-medium">
          {{ saveError }}
        </p>

        <!-- Navigation Hints -->
        <div
          :style="{
            borderTopColor: 'var(--console-play-save-separator-border)',
          }"
          class="mt-4 pt-3 border-t"
        >
          <NavigationText
            :show-navigation="true"
            :show-select="true"
            :show-back="true"
            :show-toggle-favorite="false"
            :show-menu="false"
            :is-modal="true"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
#game {
  width: 100%;
  height: 100%;
}

/* Hide the EmulatorJS in-UI exit button */
#game .ejs_menu_bar .ejs_menu_button:nth-child(-1) {
  display: none;
}
</style>
