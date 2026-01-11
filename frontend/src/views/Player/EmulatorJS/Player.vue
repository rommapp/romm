<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useTheme } from "vuetify";
import type {
  FirmwareSchema,
  SaveSchema,
  StateSchema,
  NetplayICEServer,
} from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import { saveApi as api } from "@/services/api/save";
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
  saveState,
  loadEmulatorJSSave,
  loadEmulatorJSState,
  createQuickLoadButton,
  createSaveQuitButton,
  createExitEmulationButton,
} from "./utils";

const INVALID_CHARS_REGEX = /[#<$+%>!`&*'|{}/\\?"=@:^\r\n]/gi;

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
}>();
const romRef = ref<DetailedRom>(props.rom);
const saveRef = ref<SaveSchema | null>(props.save);
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
    EJS_netplayUrl: string;
    EJS_netplayServer: string;
    EJS_netplayICEServers: NetplayICEServer[];
    EJS_netplayToken?: string;
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
      screenshot: ArrayBuffer;
      state: ArrayBuffer;
    }) => void;
    EJS_onLoadState: () => void;
    EJS_onSaveSave: (args: {
      screenshot: ArrayBuffer;
      save: ArrayBuffer;
    }) => void;
    EJS_onLoadSave: () => void;
  }
}

const supportedCores = getSupportedEJSCores(romRef.value.platform_slug);
window.EJS_core =
  supportedCores.find((core) => core === props.core) ?? supportedCores[0];
window.EJS_controlScheme = getControlSchemeForPlatform(
  romRef.value.platform_slug
);
window.EJS_threads = areThreadsRequiredForEJSCore(window.EJS_core);
window.EJS_gameID = romRef.value.id;
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
const coreOptions = configStore.getEJSCoreOptions(props.core);
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
} = configStore.config;
// EmulatorJS-SFU expects `window.EJS_netplayUrl`.
// This value is used as both:
// - Socket.IO URL (io(netplayUrl))
// - HTTP room listing base (netplayUrl + "/list")
// If the URL contains a path (e.g. /netplay), Socket.IO treats it as a namespace.
// Our SFU serves the default namespace, so we keep this at the origin.
window.EJS_netplayUrl = EJS_NETPLAY_ENABLED ? window.location.origin : "";
// Compatibility with other EmulatorJS builds, potentially compatbile with an ICE fallback build.
window.EJS_netplayServer = window.EJS_netplayUrl;
window.EJS_netplayICEServers = EJS_NETPLAY_ENABLED
  ? EJS_NETPLAY_ICE_SERVERS
  : [];
window.EJS_DEBUG_XX = EJS_DEBUG;
window.EJS_disableAutoUnload = EJS_DISABLE_AUTO_UNLOAD;
window.EJS_disableBatchBootup = EJS_DISABLE_BATCH_BOOTUP;
if (EJS_CACHE_LIMIT !== null) window.EJS_CacheLimit = EJS_CACHE_LIMIT;

onMounted(() => {
  window.scrollTo(0, 0);
  if (props.bios) {
    localStorage.setItem(
      `player:${romRef.value.platform_slug}:bios_id`,
      props.bios.id.toString()
    );
  } else {
    localStorage.removeItem(`player:${romRef.value.platform_slug}:bios_id`);
  }

  if (props.core) {
    localStorage.setItem(
      `player:${romRef.value.platform_slug}:core`,
      props.core
    );
  } else {
    localStorage.removeItem(`player:${romRef.value.platform_slug}:core`);
  }

  if (props.disc) {
    localStorage.setItem(
      `player:${romRef.value.id}:disc`,
      props.disc.toString()
    );
  } else {
    localStorage.removeItem(`player:${romRef.value.id}:disc`);
  }

  emitter?.on("saveSelected", loadSave);
  emitter?.on("stateSelected", loadState);
});

onBeforeUnmount(async () => {
  emitter?.off("saveSelected", loadSave);
  emitter?.off("stateSelected", loadState);
  window.EJS_emulator?.callEvent("exit");
  fullScreen.value = false;
  playing.value = false;
});

function displayMessage(
  message: string,
  {
    duration,
    className = "msg-info",
    icon = "",
  }: {
    duration: number;
    className?: "msg-info" | "msg-error" | "msg-success";
    icon?: string;
  }
) {
  window.EJS_emulator.displayMessage(message, duration);
  const element = document.querySelector("#game .ejs_message");
  if (element) {
    element.classList.add(className, icon);
    setTimeout(() => {
      element.classList.remove(className, icon);
    }, duration);
  }
}

// Saves management
async function loadSave(save: SaveSchema) {
  saveRef.value = save;

  const { data } = await api.get(save.download_path.replace("/api", ""), {
    responseType: "arraybuffer",
  });
  if (data) {
    loadEmulatorJSSave(new Uint8Array(data));
    displayMessage("Save loaded from server", {
      duration: 3000,
      icon: "mdi-cloud-download-outline",
    });
    return;
  }

  const file = await window.EJS_emulator.selectFile();
  loadEmulatorJSSave(new Uint8Array(await file.arrayBuffer()));
}

window.EJS_onLoadSave = async function () {
  window.EJS_emulator.pause();
  window.EJS_emulator.toggleFullscreen(false);
  emitter?.emit("selectSaveDialog", romRef.value);
};

window.EJS_onSaveSave = async function ({
  save: saveFile,
  screenshot: screenshotFile,
}) {
  const save = await saveSave({
    rom: romRef.value,
    save: saveRef.value,
    saveFile,
    screenshotFile,
  });

  romsStore.update(romRef.value);

  if (save) {
    displayMessage("Save synced with server", {
      duration: 4000,
      icon: "mdi-cloud-sync",
    });
  } else {
    displayMessage("Error syncing save with server", {
      duration: 4000,
      className: "msg-error",
      icon: "mdi-sync-alert",
    });
  }
};

// States management
async function loadState(state: StateSchema) {
  const { data } = await api.get(state.download_path.replace("/api", ""), {
    responseType: "arraybuffer",
  });
  if (data) {
    loadEmulatorJSState(new Uint8Array(data));
    displayMessage("State loaded from server", {
      duration: 3000,
      icon: "mdi-cloud-download-outline",
    });
    return;
  }

  const file = await window.EJS_emulator.selectFile();
  loadEmulatorJSState(new Uint8Array(await file.arrayBuffer()));
}

window.EJS_onLoadState = async function () {
  window.EJS_emulator.pause();
  window.EJS_emulator.toggleFullscreen(false);
  emitter?.emit("selectStateDialog", romRef.value);
};

window.EJS_onSaveState = async function ({
  state: stateFile,
  screenshot: screenshotFile,
}) {
  const state = await saveState({
    rom: romRef.value,
    stateFile,
    screenshotFile,
  });
  window.EJS_emulator.storage.states.put(
    window.EJS_emulator.getBaseFileName() + ".state",
    stateFile
  );

  romsStore.update(romRef.value);

  if (state) {
    displayMessage("State synced with server", {
      duration: 4000,
      icon: "mdi-cloud-sync",
    });
  } else {
    displayMessage("Error syncing state with server", {
      duration: 4000,
      className: "msg-error",
      icon: "mdi-sync-alert",
    });
  }
};

window.EJS_onGameStart = async () => {
  setTimeout(async () => {
    if (props.save) await loadSave(props.save);
    if (props.state) await loadState(props.state);

    window.EJS_emulator.settings = {
      ...window.EJS_emulator.settings,
      "save-state-location": "browser",
    };
  }, 10);

  const quickLoad = createQuickLoadButton();
  quickLoad.addEventListener("click", () => {
    if (
      window.EJS_emulator.settings["save-state-location"] === "browser" &&
      window.EJS_emulator.saveInBrowserSupported()
    ) {
      window.EJS_emulator.storage.states
        .get(window.EJS_emulator.getBaseFileName() + ".state")
        .then((e: Uint8Array) => {
          window.EJS_emulator.gameManager.loadState(e);
          displayMessage("Quick load from server", {
            duration: 3000,
            icon: "mdi-flash",
          });
        });
    }
  });

  const exitEmulation = createExitEmulationButton();
  exitEmulation.addEventListener("click", async () => {
    if (!romRef.value || !window.EJS_emulator) return immediateExit();
    romsStore.update(romRef.value);
    immediateExit();
  });

  const saveAndQuit = createSaveQuitButton();
  saveAndQuit.addEventListener("click", async () => {
    if (!romRef.value || !window.EJS_emulator) return immediateExit();

    const stateFile = window.EJS_emulator.gameManager.getState();
    const saveFile = window.EJS_emulator.gameManager.getSaveFile();
    const screenshotFile = await window.EJS_emulator.gameManager.screenshot();

    // Force a save of the current state
    await saveState({
      rom: romRef.value,
      stateFile,
      screenshotFile,
    });

    // Force a save of the save file
    await saveSave({
      rom: romRef.value,
      save: saveRef.value,
      saveFile,
      screenshotFile,
    });

    romsStore.update(romRef.value);
    immediateExit();
  });
};

function immediateExit() {
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

#game .ejs_message {
  visibility: hidden;
  margin: 1rem;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  color: white;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  filter: opacity(0.85) drop-shadow(0 0 0.5rem rgba(0, 0, 0, 0.5));
}

#game .ejs_message::before {
  margin-right: 8px;
  font-size: 20px !important;
  font: normal normal normal 24px / 1 "Material Design Icons";
}

#game .ejs_message.msg-info {
  visibility: visible;
  background-color: rgba(var(--v-theme-romm-blue));
}

#game .ejs_message.msg-error {
  visibility: visible;
  background-color: rgba(var(--v-theme-romm-red));
}

#game .ejs_message.msg-success {
  visibility: visible;
  background-color: rgba(var(--v-theme-romm-green));
}
</style>
