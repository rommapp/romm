import type {
  ConfigResponse,
  EjsControlsButton,
  FirmwareSchema,
  NetplayICEServer,
} from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import {
  areThreadsRequiredForEJSCore,
  getControlSchemeForPlatform,
  getDownloadPath,
  getSupportedEJSCores,
} from "@/utils";
import { firmwareExternalFiles } from "@/utils/playerFirmware";

// EmulatorJS reads its whole configuration from these globals when its loader
// script runs, and calls the callbacks back on `window` later.
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
    EJS_Buttons: Record<string, boolean | { displayName: string }>;
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
    // Only the 4.2.3 build exposes its GameManager class as a global.
    EJS_GameManager?: {
      prototype: {
        writeFile(path: string, data: unknown): void;
        __rommBytesPatched?: boolean;
      };
    };
    // Socket.IO global, bundled by EmulatorJS and used by its netplay code.
    io?: ((url: string, opts?: Record<string, unknown>) => unknown) & {
      __rommNetplayPatched?: boolean;
    };
  }
}

const INVALID_CHARS_REGEX = /[#<$+%>!`&*'|{}/\\?"=@:^\r\n]/gi;

type EjsControls = Record<number, Record<number, EjsControlsButton>>;

export type EjsConfig = Pick<
  Window,
  | "EJS_core"
  | "EJS_controlScheme"
  | "EJS_threads"
  | "EJS_gameID"
  | "EJS_gameUrl"
  | "EJS_biosUrl"
  | "EJS_externalFiles"
  | "EJS_player"
  | "EJS_color"
  | "EJS_alignStartButton"
  | "EJS_startOnLoaded"
  | "EJS_backgroundImage"
  | "EJS_backgroundColor"
  | "EJS_Buttons"
  | "EJS_defaultOptions"
  | "EJS_gameName"
  | "EJS_language"
  | "EJS_disableAutoLang"
  | "EJS_netplayServer"
  | "EJS_netplayICEServers"
  | "EJS_DEBUG_XX"
  | "EJS_disableAutoUnload"
  | "EJS_disableBatchBootup"
> &
  Partial<Pick<Window, "EJS_defaultControls" | "EJS_CacheLimit">>;

export interface EjsConfigInput {
  rom: DetailedRom;
  /** The core the player picked, if any; an unsupported one falls back. */
  core: string | null;
  disc: number | null;
  bios: FirmwareSchema | null;
  firmware: FirmwareSchema[];
  loadStateLabel?: string | undefined;
  config: Pick<
    ConfigResponse,
    | "EJS_DEBUG"
    | "EJS_CACHE_LIMIT"
    | "EJS_DISABLE_AUTO_UNLOAD"
    | "EJS_DISABLE_BATCH_BOOTUP"
    | "EJS_ENABLE_AUTO_SAVE_SYNC"
    | "EJS_NETPLAY_ENABLED"
    | "EJS_NETPLAY_ICE_SERVERS"
  >;
  coreOptions: (core: string) => Record<string, string | boolean>;
  controls: EjsControls | null;
  /** RomM's locale code, like `en_US`. */
  locale: string;
  origin: string;
  backgroundColor: string;
  t: (key: string) => string;
}

/** The EmulatorJS globals for one launch, computed without touching `window`. */
export function buildEjsConfig(input: EjsConfigInput): EjsConfig {
  const { rom, config, t } = input;
  const supportedCores = getSupportedEJSCores(
    rom.platform_slug,
    config.EJS_NETPLAY_ENABLED,
  );
  const core =
    supportedCores.find((supported) => supported === input.core) ??
    supportedCores[0]!;

  return {
    EJS_core: core,
    EJS_controlScheme: getControlSchemeForPlatform(rom.platform_slug),
    EJS_threads: areThreadsRequiredForEJSCore(core),
    EJS_gameID: rom.id,
    EJS_gameUrl: getDownloadPath({
      rom,
      fileIDs: input.disc ? [input.disc] : [],
      purpose: "play",
    }),
    EJS_biosUrl: input.bios
      ? `/api/firmware/${input.bios.id}/content/${input.bios.file_name}`
      : "",
    EJS_externalFiles: firmwareExternalFiles(core, input.firmware),
    EJS_player: "#game",
    EJS_color: "#A453FF",
    EJS_alignStartButton: "center",
    EJS_startOnLoaded: true,
    EJS_backgroundImage: `${input.origin}/assets/logos/romm_logo_xbox_one_circle_boot.svg`,
    EJS_backgroundColor: input.backgroundColor,
    // Labels come from RomM's locales, which cover languages EmulatorJS does not.
    EJS_Buttons: {
      // RomM draws its own exit button.
      exitEmulation: false,
      // Saves load from the picker. Without auto-sync, Sync save uploads on demand.
      saveSavFiles: config.EJS_ENABLE_AUTO_SAVE_SYNC
        ? false
        : { displayName: t("play.sync-save") },
      loadSavFiles: false,
      restart: { displayName: t("play.restart") },
      pause: { displayName: t("play.pause") },
      play: { displayName: t("play.resume") },
      saveState: { displayName: t("play.save-state") },
      loadState: { displayName: input.loadStateLabel ?? t("play.load-state") },
      gamepad: { displayName: t("play.control-settings") },
      cheat: { displayName: t("play.cheats") },
      cacheManager: { displayName: t("play.cache-manager") },
      netplay: { displayName: t("play.netplay") },
      mute: { displayName: t("play.mute") },
      unmute: { displayName: t("play.unmute") },
      diskButton: { displayName: t("play.discs") },
      settings: { displayName: t("common.settings") },
      enterFullscreen: { displayName: t("play.full-screen") },
      exitFullscreen: { displayName: t("play.exit-full-screen") },
    },
    EJS_defaultOptions: {
      // Saves and states go to the browser, and RomM syncs them from there.
      "save-state-location": "browser",
      rewindEnabled: "enabled",
      ...input.coreOptions(core),
    },
    ...(input.controls ? { EJS_defaultControls: input.controls } : {}),
    EJS_gameName: rom.fs_name_no_tags.replace(INVALID_CHARS_REGEX, "").trim(),
    EJS_language: input.locale.replace("_", "-"),
    EJS_disableAutoLang: true,
    EJS_netplayServer: config.EJS_NETPLAY_ENABLED ? input.origin : "",
    EJS_netplayICEServers: config.EJS_NETPLAY_ENABLED
      ? config.EJS_NETPLAY_ICE_SERVERS
      : [],
    EJS_DEBUG_XX: config.EJS_DEBUG,
    EJS_disableAutoUnload: config.EJS_DISABLE_AUTO_UNLOAD,
    EJS_disableBatchBootup: config.EJS_DISABLE_BATCH_BOOTUP,
    ...(config.EJS_CACHE_LIMIT !== null
      ? { EJS_CacheLimit: config.EJS_CACHE_LIMIT }
      : {}),
  };
}

/** Hand a launch's configuration to EmulatorJS, before its loader runs. */
export function applyEjsGlobals(config: EjsConfig): void {
  Object.assign(window, config);
}
