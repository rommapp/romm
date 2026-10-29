import { afterEach, describe, expect, it } from "vitest";
import { firmwareFixture } from "@/utils/firmware.fixtures";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import {
  applyEjsGlobals,
  buildEjsConfig,
  type EjsConfigInput,
} from "./emulatorJSConfig";

const rom = detailedRomFixture({
  id: 7,
  platform_slug: "psx",
  fs_name: "Chrono Cross (USA) (Disc 1).chd",
  fs_name_no_tags: "Chrono Cross: <Disc 1>?",
  files: [],
});

const bios = firmwareFixture({ id: 3, file_name: "scph5501.bin" });

function input(overrides: Partial<EjsConfigInput> = {}): EjsConfigInput {
  return {
    rom,
    core: null,
    disc: null,
    bios: null,
    firmware: [],
    config: {
      EJS_DEBUG: false,
      EJS_CACHE_LIMIT: null,
      EJS_DISABLE_AUTO_UNLOAD: false,
      EJS_DISABLE_BATCH_BOOTUP: false,
      EJS_ENABLE_AUTO_SAVE_SYNC: false,
      EJS_NETPLAY_ENABLED: false,
      EJS_NETPLAY_ICE_SERVERS: [],
    },
    coreOptions: (core) => ({ [`${core}-option`]: "on" }),
    controls: null,
    locale: "pt_BR",
    origin: "https://romm.example",
    backgroundColor: "rgb(18, 18, 18)",
    t: (key) => `t(${key})`,
    ...overrides,
  };
}

describe("buildEjsConfig", () => {
  it("builds a launch with the platform's default core", () => {
    const config = buildEjsConfig(input());
    expect(config).toMatchObject({
      EJS_core: "pcsx_rearmed",
      EJS_gameUrl:
        "/api/roms/7/content/Chrono%20Cross%20(USA)%20(Disc%201).chd?purpose=play",
      EJS_biosUrl: "",
      EJS_netplayServer: "",
      EJS_netplayICEServers: [],
      EJS_DEBUG_XX: false,
    });
    expect(config.EJS_Buttons).toMatchObject({
      saveSavFiles: { displayName: "t(play.sync-save)" },
      loadState: { displayName: "t(play.load-state)" },
    });
  });

  it("builds a launch with every optional setting on", () => {
    const label = (key: string) => ({ displayName: `t(${key})` });
    expect(
      buildEjsConfig(
        input({
          core: "mednafen_psx_hw",
          disc: 42,
          bios,
          loadStateLabel: "Load from RomM",
          controls: { 0: { 0: { value: "x" } } },
          config: {
            EJS_DEBUG: true,
            EJS_CACHE_LIMIT: 1024,
            EJS_DISABLE_AUTO_UNLOAD: true,
            EJS_DISABLE_BATCH_BOOTUP: true,
            EJS_ENABLE_AUTO_SAVE_SYNC: true,
            EJS_NETPLAY_ENABLED: true,
            EJS_NETPLAY_ICE_SERVERS: [{ urls: "stun:stun.example:3478" }],
          },
        }),
      ),
    ).toEqual({
      EJS_core: "mednafen_psx_hw",
      EJS_controlScheme: null,
      EJS_threads: false,
      EJS_gameID: 7,
      EJS_gameUrl:
        "/api/roms/7/content/Chrono%20Cross%20(USA)%20(Disc%201).chd?file_ids=42&purpose=play",
      EJS_biosUrl: "/api/firmware/3/content/scph5501.bin",
      EJS_externalFiles: {},
      EJS_player: "#game",
      EJS_color: "#A453FF",
      EJS_alignStartButton: "center",
      EJS_startOnLoaded: true,
      EJS_backgroundImage:
        "https://romm.example/assets/logos/romm_logo_xbox_one_circle_boot.svg",
      EJS_backgroundColor: "rgb(18, 18, 18)",
      EJS_Buttons: {
        exitEmulation: false,
        saveSavFiles: false,
        loadSavFiles: false,
        restart: label("play.restart"),
        pause: label("play.pause"),
        play: label("play.resume"),
        saveState: label("play.save-state"),
        loadState: { displayName: "Load from RomM" },
        gamepad: label("play.control-settings"),
        cheat: label("play.cheats"),
        cacheManager: label("play.cache-manager"),
        netplay: label("play.netplay"),
        mute: label("play.mute"),
        unmute: label("play.unmute"),
        diskButton: label("play.discs"),
        settings: label("common.settings"),
        enterFullscreen: label("play.full-screen"),
        exitFullscreen: label("play.exit-full-screen"),
      },
      EJS_defaultOptions: {
        "save-state-location": "browser",
        rewindEnabled: "enabled",
        "mednafen_psx_hw-option": "on",
      },
      EJS_defaultControls: { 0: { 0: { value: "x" } } },
      EJS_gameName: "Chrono Cross Disc 1",
      EJS_language: "pt-BR",
      EJS_disableAutoLang: true,
      EJS_netplayServer: "https://romm.example",
      EJS_netplayICEServers: [{ urls: "stun:stun.example:3478" }],
      EJS_DEBUG_XX: true,
      EJS_disableAutoUnload: true,
      EJS_disableBatchBootup: true,
      EJS_CacheLimit: 1024,
    });
  });

  it("falls back to a supported core when the picked one is not", () => {
    const config = buildEjsConfig(input({ core: "not-a-core" }));
    expect(config.EJS_core).toBe(buildEjsConfig(input()).EJS_core);
    expect(config.EJS_defaultOptions).toMatchObject({
      [`${config.EJS_core}-option`]: "on",
    });
  });

  it("leaves out the controls and cache limit nothing configured", () => {
    const config = buildEjsConfig(input());
    expect(config).not.toHaveProperty("EJS_defaultControls");
    expect(config).not.toHaveProperty("EJS_CacheLimit");
  });
});

describe("applyEjsGlobals", () => {
  afterEach(() => {
    for (const key of Object.keys(buildEjsConfig(input()))) {
      Reflect.deleteProperty(window, key);
    }
  });

  it("puts every value on window", () => {
    const config = buildEjsConfig(input());
    applyEjsGlobals(config);
    for (const [key, value] of Object.entries(config)) {
      expect(Reflect.get(window, key)).toEqual(value);
    }
  });
});
