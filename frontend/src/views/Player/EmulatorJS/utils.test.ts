import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  createSaveSyncTracker,
  hashSaveFile,
  installEJSDefaultOptionsTrap,
} from "./utils";

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

describe("createSaveSyncTracker", () => {
  it("uploads only once the bytes have been stable for two ticks", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed("server");
    // The first tick with new bytes may be a save the core is mid-write on.
    expect(tracker.shouldUpload("a")).toBe(false);
    // The second identical tick proves it settled.
    expect(tracker.shouldUpload("a")).toBe(true);
  });

  it("uploads nothing while the save is unchanged from the last upload", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed("server");
    expect(tracker.shouldUpload("server")).toBe(false);
    expect(tracker.shouldUpload("server")).toBe(false);
    expect(tracker.shouldUpload("a")).toBe(false);
    expect(tracker.shouldUpload("a")).toBe(true);
    tracker.markUploaded("a");
    expect(tracker.shouldUpload("a")).toBe(false);
    expect(tracker.shouldUpload("a")).toBe(false);
  });

  it("never uploads a value that keeps changing between ticks", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(null);
    expect(tracker.shouldUpload("a")).toBe(false);
    expect(tracker.shouldUpload("b")).toBe(false);
    expect(tracker.shouldUpload("c")).toBe(false);
    expect(tracker.shouldUpload("c")).toBe(true);
  });

  it("re-offers a save whose upload failed", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed("server");
    tracker.shouldUpload("a");
    expect(tracker.shouldUpload("a")).toBe(true);
    // No markUploaded: the upload failed. The next stable tick tries again.
    expect(tracker.shouldUpload("a")).toBe(true);
  });
});

describe("hashSaveFile", () => {
  it("returns null for missing or empty bytes", async () => {
    expect(await hashSaveFile(null)).toBeNull();
    expect(await hashSaveFile(undefined)).toBeNull();
    expect(await hashSaveFile(new Uint8Array(0))).toBeNull();
  });

  it("falls back to a JS hash when WebCrypto is unavailable", async () => {
    // subtle lives on the prototype; an own property shadows it, delete restores it.
    Object.defineProperty(globalThis.crypto, "subtle", {
      value: undefined,
      configurable: true,
    });
    try {
      const a = await hashSaveFile(new Uint8Array([1, 2, 3]));
      const b = await hashSaveFile(new Uint8Array([1, 2, 3]));
      const c = await hashSaveFile(new Uint8Array([1, 2, 4]));
      expect(a).toBe(b);
      expect(a).not.toBe(c);
      expect(a).toMatch(/^[0-9a-f]{16}$/);
    } finally {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (globalThis.crypto as any).subtle;
    }
  });

  it("hashes content, not identity", async () => {
    const a = await hashSaveFile(new Uint8Array([1, 2, 3]));
    const b = await hashSaveFile(new Uint8Array([1, 2, 3]).buffer);
    const c = await hashSaveFile(new Uint8Array([1, 2, 4]));
    expect(a).toBe(b);
    expect(a).not.toBe(c);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });
});
