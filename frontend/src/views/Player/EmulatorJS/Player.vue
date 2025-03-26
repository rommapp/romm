<script setup lang="ts">
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import { saveApi as api } from "@/services/api/save";
import type { DetailedRom } from "@/stores/roms";
import {
  areThreadsRequiredForEJSCore,
  getSupportedEJSCores,
  getControlSchemeForPlatform,
  getDownloadPath,
} from "@/utils";
import SelectSave from "@/components/common/Game/Dialog/Asset/SelectSave.vue";
import SelectState from "@/components/common/Game/Dialog/Asset/SelectState.vue";
import { inject, onBeforeUnmount, onMounted } from "vue";
import { useTheme } from "vuetify";
import {
  saveSave,
  saveState,
  loadEmulatorJSSave,
  loadEmulatorJSState,
} from "./utils";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

const INVALID_CHARS_REGEX = /[#<$+%>!`&*'|{}/\\?"=@:^\r\n]/gi;

const props = defineProps<{
  rom: DetailedRom;
  save: SaveSchema | null;
  state: StateSchema | null;
  bios: FirmwareSchema | null;
  core: string | null;
  disc: number | null;
}>();
const theme = useTheme();
const emitter = inject<Emitter<Events>>("emitter");

// Declare global variables for EmulatorJS
declare global {
  interface Window {
    EJS_core: string;
    EJS_biosUrl: string;
    EJS_player: string;
    EJS_pathtodata: string;
    EJS_color: string;
    EJS_defaultOptions: object;
    EJS_gameID: number;
    EJS_gameName: string;
    EJS_backgroundImage: string;
    EJS_backgroundColor: string;
    EJS_gameUrl: string;
    EJS_loadStateURL: string | null;
    EJS_cheats: string;
    EJS_gamePatchUrl: string;
    EJS_netplayServer: string;
    EJS_alignStartButton: "top" | "center" | "bottom";
    EJS_startOnLoaded: boolean;
    EJS_fullscreenOnLoaded: boolean;
    EJS_threads: boolean;
    EJS_controlScheme: string | null;
    EJS_emulator: any; // eslint-disable-line @typescript-eslint/no-explicit-any
    EJS_Buttons: Record<string, boolean>;
    EJS_onGameStart: () => void;
    EJS_onSaveState: (args: {
      screenshot: Uint8Array;
      state: Uint8Array;
    }) => void;
    EJS_onLoadState: () => void;
    EJS_onSaveSave: (args: {
      screenshot: Uint8Array;
      save: Uint8Array;
    }) => void;
    EJS_onLoadSave: () => void;
  }
}

const supportedCores = getSupportedEJSCores(props.rom.platform_slug);
window.EJS_core =
  supportedCores.find((core) => core === props.core) ?? supportedCores[0];
window.EJS_controlScheme = getControlSchemeForPlatform(props.rom.platform_slug);
window.EJS_threads = areThreadsRequiredForEJSCore(window.EJS_core);
window.EJS_gameID = props.rom.id;
window.EJS_gameUrl = getDownloadPath({
  rom: props.rom,
  fileIDs: props.disc ? [props.disc] : [],
});
window.EJS_biosUrl = props.bios
  ? `/api/firmware/${props.bios.id}/content/${props.bios.file_name}`
  : "";
window.EJS_player = "#game";
window.EJS_color = "#A453FF";
window.EJS_alignStartButton = "center";
window.EJS_startOnLoaded = true;
window.EJS_backgroundImage = `${window.location.origin}/assets/emulatorjs/powered_by_emulatorjs.png`;
window.EJS_backgroundColor = theme.current.value.colors.background;
// Force saving saves and states to the browser
window.EJS_defaultOptions = {
  "save-state-location": "browser",
  rewindEnabled: "enabled",
};
// Set a valid game name
window.EJS_gameName = props.rom.fs_name_no_tags
  .replace(INVALID_CHARS_REGEX, "")
  .trim();
// Disable quick save and quick load
window.EJS_Buttons = {
  quickSave: false,
  quickLoad: false,
};

function onBeforeUnload(event: BeforeUnloadEvent) {
  event.preventDefault();
  event.returnValue =
    "Use the 'save and quit' button to save your progress and close the game.";
}

onMounted(() => {
  if (props.save) {
    localStorage.setItem(
      `player:${props.rom.id}:save_id`,
      props.save.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${props.rom.id}:save_id`);
  }

  if (props.state) {
    localStorage.setItem(
      `player:${props.rom.id}:state_id`,
      props.state.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${props.rom.id}:state_id`);
  }

  if (props.bios) {
    localStorage.setItem(
      `player:${props.rom.platform_slug}:bios_id`,
      props.bios.id.toString(),
    );
  } else {
    localStorage.removeItem(`player:${props.rom.platform_slug}:bios_id`);
  }

  if (props.core) {
    localStorage.setItem(`player:${props.rom.platform_slug}:core`, props.core);
  } else {
    localStorage.removeItem(`player:${props.rom.platform_slug}:core`);
  }

  if (props.disc) {
    localStorage.setItem(`player:${props.rom.id}:disc`, props.disc.toString());
  } else {
    localStorage.removeItem(`player:${props.rom.id}:disc`);
  }

  emitter?.on("saveSelected", loadSave);
  emitter?.on("stateSelected", loadState);
});

onBeforeUnmount(async () => {
  window.removeEventListener("beforeunload", onBeforeUnload);
  emitter?.off("saveSelected", loadSave);
  emitter?.off("stateSelected", loadState);
});

// Saves management
async function loadSave(save: SaveSchema) {
  window.EJS_emulator.play();

  const { data } = await api.get(save.download_path.replace("/api", ""), {
    responseType: "arraybuffer",
  });
  if (data) {
    loadEmulatorJSSave(new Uint8Array(data));
    return;
  }

  const file = await window.EJS_emulator.selectFile();
  loadEmulatorJSSave(new Uint8Array(await file.arrayBuffer()));
}

window.EJS_onLoadSave = async function () {
  window.EJS_emulator.pause();
  emitter?.emit("selectSaveDialog", props.rom);
};

window.EJS_onSaveSave = async function ({
  save: saveFile,
  screenshot: screenshotFile,
}) {
  await saveSave({
    rom: props.rom,
    saveFile,
    screenshotFile,
  });
  window.EJS_emulator.storage.states.put(
    window.EJS_emulator.getBaseFileName() + ".state",
    saveFile,
  );
};

// States management
async function loadState(state: StateSchema) {
  window.EJS_emulator.play();

  const { data } = await api.get(state.download_path.replace("/api", ""), {
    responseType: "arraybuffer",
  });
  if (data) {
    loadEmulatorJSState(new Uint8Array(data));
    return;
  }

  const file = await window.EJS_emulator.selectFile();
  loadEmulatorJSState(new Uint8Array(await file.arrayBuffer()));
}

window.EJS_onLoadState = async function () {
  window.EJS_emulator.pause();
  emitter?.emit("selectStateDialog", props.rom);
};

window.EJS_onSaveState = async function ({
  state: stateFile,
  screenshot: screenshotFile,
}) {
  const state = await saveState({
    rom: props.rom,
    stateFile,
    screenshotFile,
  });
  window.EJS_emulator.storage.states.put(
    window.EJS_emulator.getBaseFileName() + ".state",
    state,
  );
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

  window.addEventListener("beforeunload", onBeforeUnload);
};
</script>

<template>
  <div id="game" />
  <select-save />
  <select-state />
</template>

<style scoped>
#game {
  height: 100%;
}
</style>

<style>
#game .ejs_cheat_code {
  background-color: white;
}

#game .ejs_settings_transition {
  height: fit-content;
}

#game .ejs_setting_menu .ejs_settings_main_bar:nth-child(3) {
  display: none;
}

#game .ejs_game_background {
  background-size: 40%;
}

#game .ejs_menu_bar .ejs_menu_button:last-child {
  display: none;
}
</style>

<!-- Other config options: https://emulatorjs.org/docs/options -->

<!-- window.EJS_biosUrl; -->
<!-- window.EJS_VirtualGamepadSettings; -->
<!-- window.EJS_cheats; -->
<!-- window.EJS_gamePatchUrl; -->
<!-- window.EJS_gameParentUrl; -->
<!-- window.EJS_netplayServer; -->
