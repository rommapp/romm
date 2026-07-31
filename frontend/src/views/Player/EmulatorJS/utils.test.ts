import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { installEJSDefaultOptionsTrap } from "./utils";

const STORAGE_KEY = "ejs-7-n64-Test Game-settings";

// Mimics the upstream EmulatorJS 4.2.3 instance closely enough to exercise
// the two buggy code paths the trap patches: preGetSetting short-circuiting
// to the saved-settings object, and getCoreSettings returning "" when
// localStorage holds no saved entry.
/* eslint-disable @typescript-eslint/no-explicit-any */
function makeEmulator(defaultOptions: Record<string, unknown>): any {
  return {
    config: { defaultOptions, gameId: 7 },
    supportsWebgl2: true,
    rewindEnabled: false,
    videoRotation: undefined,
    webgl2Enabled: null,
    getLocalStorageKey() {
      return STORAGE_KEY;
    },
    preGetSetting(setting: string) {
      const raw = localStorage.getItem(this.getLocalStorageKey());
      try {
        const coreSpecific = raw ? JSON.parse(raw) : null;
        if (coreSpecific && coreSpecific.settings) {
          return coreSpecific.settings[setting];
        }
      } catch {
        // fall through, same as upstream
      }
      if (this.config.defaultOptions && this.config.defaultOptions[setting]) {
        return this.config.defaultOptions[setting];
      }
      return null;
    },
    getCoreSettings() {
      const raw = localStorage.getItem(this.getLocalStorageKey());
      if (raw) {
        const coreSpecific = JSON.parse(raw);
        let rv = "";
        for (const k in coreSpecific.settings) {
          rv += `${k} = "${coreSpecific.settings[k]}"\n`;
        }
        return rv;
      }
      return "";
    },
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function saveSettings(settings: Record<string, unknown>) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ controlSettings: {}, settings, cheats: [] }),
  );
}

describe("installEJSDefaultOptionsTrap", () => {
  beforeEach(() => {
    localStorage.clear();
    installEJSDefaultOptionsTrap();
  });

  afterEach(() => {
    delete (window as { EJS_emulator?: unknown }).EJS_emulator;
    localStorage.clear();
  });

  it("patches the instance when window.EJS_emulator is assigned", () => {
    const emulator = makeEmulator({});
    window.EJS_emulator = emulator;
    expect(window.EJS_emulator.__rommSettingsPatched).toBe(true);
  });

  it("falls back to defaults for keys missing from saved settings", () => {
    // Once any setting is saved, upstream preGetSetting returns undefined
    // for every key the user never touched (issue #3908).
    saveSettings({ shader: "crt-easymode.glslp" });
    const emulator = makeEmulator({ vsync: "disabled" });
    window.EJS_emulator = emulator;

    expect(emulator.preGetSetting("shader")).toBe("crt-easymode.glslp");
    expect(emulator.preGetSetting("vsync")).toBe("disabled");
    expect(emulator.preGetSetting("unknown")).toBe(null);
  });

  it("includes default core options on a fresh launch", () => {
    // Upstream getCoreSettings returns "" when localStorage has no saved
    // entry, dropping config.yaml core options entirely (issue #3946).
    const emulator = makeEmulator({
      "mupen64plus-FXAA": "1",
      "mupen64plus-OverscanTop": "11",
    });
    window.EJS_emulator = emulator;

    const output = emulator.getCoreSettings();
    expect(output).toContain("mupen64plus-FXAA = 1");
    expect(output).toContain("mupen64plus-OverscanTop = 11");
  });

  it("lets saved settings override default core options", () => {
    saveSettings({ "mupen64plus-FXAA": "0", shader: "crt-easymode.glslp" });
    const emulator = makeEmulator({
      "mupen64plus-FXAA": "1",
      "mupen64plus-OverscanTop": "11",
    });
    window.EJS_emulator = emulator;

    const output = emulator.getCoreSettings();
    expect(output).toContain("mupen64plus-FXAA = 0");
    expect(output).toContain("mupen64plus-OverscanTop = 11");
    expect(output).toContain('shader = "crt-easymode.glslp"');
  });

  it("recomputes constructor-captured values from defaults", () => {
    saveSettings({ shader: "crt-easymode.glslp" });
    const emulator = makeEmulator({
      rewindEnabled: "enabled",
      webgl2Enabled: "enabled",
    });
    window.EJS_emulator = emulator;

    expect(emulator.rewindEnabled).toBe(true);
    expect(emulator.webgl2Enabled).toBe(true);
  });

  it("does not re-patch an already patched instance", () => {
    const emulator = makeEmulator({});
    window.EJS_emulator = emulator;
    const patched = emulator.preGetSetting;
    window.EJS_emulator = emulator;
    expect(emulator.preGetSetting).toBe(patched);
  });
});
