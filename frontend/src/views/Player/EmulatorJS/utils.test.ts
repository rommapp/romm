import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import type { StateSchema } from "@/__generated__";
import { sessionStateName } from "@/services/api/state";
import type { DetailedRom } from "@/stores/roms";
import {
  buildStateFormData,
  captureScreenshot,
  dumpSaveFile,
  heldFor,
  createSaveSyncTracker,
  installEJSDefaultOptionsTrap,
  pollSaveFiles,
  resolveScreenshot,
  saveSave,
  saveSaveOnUnload,
  saveState,
} from "./utils";

const saveApiMocks = vi.hoisted(() => ({
  uploadSaves: vi.fn(),
  updateSave: vi.fn(),
  sendSaveOnUnload: vi.fn(),
}));
const stateApiMocks = vi.hoisted(() => ({
  uploadStates: vi.fn(),
}));
const pendingAssetMocks = vi.hoisted(() => ({
  write: vi.fn(),
  clear: vi.fn(),
}));

vi.mock("@/services/api/save", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api/save")>()),
  default: saveApiMocks,
}));
vi.mock("@/services/api/state", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api/state")>()),
  default: stateApiMocks,
}));
vi.mock("@/services/pending-asset", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/pending-asset")>()),
  default: pendingAssetMocks,
}));

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
  const bytes = (...values: number[]) => new Uint8Array(values);
  const server = bytes(9, 9);
  const a = bytes(1, 2, 3);
  const b = bytes(4, 5, 6);

  it("uploads only once the bytes have been stable for two ticks", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(server);
    // The first tick with new bytes may be a save the core is mid-write on.
    expect(tracker.shouldUpload(a)).toBe(false);
    // The second identical tick proves it settled.
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(true);
  });

  it("uploads nothing while the save is unchanged from the last upload", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(server);
    expect(tracker.shouldUpload(bytes(9, 9))).toBe(false);
    expect(tracker.shouldUpload(bytes(9, 9))).toBe(false);
    expect(tracker.shouldUpload(a)).toBe(false);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(true);
    tracker.markUploaded(a);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(false);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(false);
  });

  it("reports pending changes without waiting for a second tick", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(server);
    expect(tracker.hasChanges(bytes(9, 9))).toBe(false);
    expect(tracker.hasChanges(a)).toBe(true);
    tracker.markUploaded(a);
    expect(tracker.hasChanges(bytes(1, 2, 3))).toBe(false);
    tracker.baseline(b);
    expect(tracker.hasChanges(bytes(4, 5, 6))).toBe(false);
    expect(tracker.hasChanges(a)).toBe(true);
  });

  it("never uploads a value that keeps changing between ticks", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(null);
    expect(tracker.shouldUpload(a)).toBe(false);
    expect(tracker.shouldUpload(b)).toBe(false);
    expect(tracker.shouldUpload(bytes(7))).toBe(false);
    expect(tracker.shouldUpload(bytes(7))).toBe(true);
  });

  it("re-offers a save whose upload failed", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(server);
    tracker.shouldUpload(a);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(true);
    // No markUploaded: the upload failed. The next stable tick tries again.
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(true);
  });

  it("knows which bytes the server already holds", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(bytes(1, 2, 3));

    expect(tracker.isUploaded(bytes(1, 2, 3))).toBe(true);
    expect(tracker.isUploaded(bytes(1, 2, 4))).toBe(false);

    tracker.markUploaded(bytes(1, 2, 4));

    expect(tracker.isUploaded(bytes(1, 2, 4))).toBe(true);
    expect(tracker.isUploaded(bytes(1, 2, 3))).toBe(false);
  });

  it("holds a baseline the tick ignores but a forced write still persists", () => {
    const tracker = createSaveSyncTracker();
    tracker.baseline(bytes(1, 2, 3));

    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(false);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(false);
    expect(tracker.isUploaded(bytes(1, 2, 3))).toBe(false);

    expect(tracker.shouldUpload(bytes(9))).toBe(false);
    expect(tracker.shouldUpload(bytes(9))).toBe(true);

    // Once something was uploaded, returning to the baseline bytes is a change.
    tracker.markUploaded(bytes(9));
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(false);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(true);
  });

  it("compares content, not identity, and treats a resize as a change", () => {
    const tracker = createSaveSyncTracker();
    tracker.seed(null);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(false);
    expect(tracker.shouldUpload(bytes(1, 2, 3))).toBe(true);
    expect(tracker.shouldUpload(bytes(1, 2, 3, 0))).toBe(false);
  });
});

describe("pollSaveFiles", () => {
  const emulatorWith = (sramBytes: number) => ({
    started: true,
    gameManager: {
      saveSaveFiles: vi.fn(),
      getSaveFile: () => new Uint8Array(sramBytes),
    },
  });

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("flushes every second while the game runs and stops on demand", () => {
    const emulator = emulatorWith(128 * 1024);
    const stop = pollSaveFiles(emulator);

    vi.advanceTimersByTime(2000);
    expect(emulator.gameManager.saveSaveFiles).toHaveBeenCalledTimes(2);

    emulator.started = false;
    vi.advanceTimersByTime(1000);
    expect(emulator.gameManager.saveSaveFiles).toHaveBeenCalledTimes(2);

    emulator.started = true;
    stop();
    vi.advanceTimersByTime(5000);
    expect(emulator.gameManager.saveSaveFiles).toHaveBeenCalledTimes(2);
  });

  it("slows down for a save too big to copy every second", () => {
    const emulator = emulatorWith(4 * 1024 * 1024);
    const stop = pollSaveFiles(emulator);

    vi.advanceTimersByTime(4095);
    expect(emulator.gameManager.saveSaveFiles).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(emulator.gameManager.saveSaveFiles).toHaveBeenCalledOnce();
    stop();
  });
});

describe("captureScreenshot", () => {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  afterEach(() => {
    delete (window as any).EJS_emulator;
  });

  it("reads the live canvas through the game manager", async () => {
    const shot = new ArrayBuffer(8);
    (window as any).EJS_emulator = {
      gameManager: { screenshot: async () => shot },
    };

    await expect(captureScreenshot()).resolves.toBe(shot);
  });

  // A save or state still has to reach the server without its picture.
  it("returns nothing when the emulator has no game manager yet", async () => {
    (window as any).EJS_emulator = {};

    await expect(captureScreenshot()).resolves.toBeUndefined();
  });

  it("swallows a capture that throws", async () => {
    (window as any).EJS_emulator = {
      gameManager: {
        screenshot: async () => {
          throw new Error("canvas is gone");
        },
      },
    };

    await expect(captureScreenshot()).resolves.toBeUndefined();
  });

  it("treats an empty readback as no picture", async () => {
    (window as any).EJS_emulator = {
      gameManager: { screenshot: async () => new ArrayBuffer(0) },
    };

    await expect(captureScreenshot()).resolves.toBeUndefined();
  });

  // EmulatorJS waits for its screenshot by polling the filesystem forever, and
  // a capture deletes the file the one before it is still waiting on.
  it("takes one capture at a time", async () => {
    const order: string[] = [];
    let release: (() => void) | undefined;
    const first = new Promise<ArrayBuffer>((resolve) => {
      release = () => resolve(new ArrayBuffer(8));
    });
    const screenshot = vi
      .fn()
      .mockImplementationOnce(() => {
        order.push("first");
        return first;
      })
      .mockImplementationOnce(async () => {
        order.push("second");
        return new ArrayBuffer(4);
      });
    (window as any).EJS_emulator = { gameManager: { screenshot } };

    const pending = [captureScreenshot(), captureScreenshot()];
    await vi.waitFor(() => expect(order).toEqual(["first"]));

    release?.();
    await Promise.all(pending);

    expect(order).toEqual(["first", "second"]);
  });

  // That poll runs for the rest of the session unless the file turns up.
  it("releases a capture that never arrived", async () => {
    vi.useFakeTimers();
    const writeFile = vi.fn();
    (window as any).EJS_emulator = {
      gameManager: {
        FS: { writeFile },
        screenshot: () => new Promise(() => {}),
      },
    };

    const capture = captureScreenshot();
    await vi.advanceTimersByTimeAsync(3000);

    await expect(capture).resolves.toBeUndefined();
    expect(writeFile).toHaveBeenCalledWith(
      "/screenshot.png",
      new Uint8Array(0),
    );
    vi.useRealTimers();
  });
});

describe("dumpSaveFile", () => {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  afterEach(() => {
    (window as any).EJS_emulator = undefined;
  });

  // A state restores the SRAM into the core's memory, not into the file, so a
  // read that skips the dump hands back bytes from before the restore.
  it("has the core write its SRAM out before reading it", () => {
    const getSaveFile = vi.fn(() => new Uint8Array([1, 2, 3]));
    (window as any).EJS_emulator = { gameManager: { getSaveFile } };

    expect(dumpSaveFile()).toEqual(new Uint8Array([1, 2, 3]));
    expect(getSaveFile).toHaveBeenCalledWith(true);
  });

  it("has nothing to offer before the emulator is up", () => {
    expect(dumpSaveFile()).toBeNull();
  });
  /* eslint-enable @typescript-eslint/no-explicit-any */
});

describe("resolveScreenshot", () => {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  afterEach(() => {
    delete (window as any).EJS_emulator;
  });

  it("prefers the live canvas over what EmulatorJS passed", async () => {
    const live = new ArrayBuffer(8);
    (window as any).EJS_emulator = {
      gameManager: { screenshot: async () => live },
    };

    await expect(resolveScreenshot(new ArrayBuffer(4))).resolves.toBe(live);
  });

  it("falls back to EmulatorJS's picture when the canvas gives none", async () => {
    const fallback = new ArrayBuffer(4);
    (window as any).EJS_emulator = {};

    await expect(resolveScreenshot(fallback)).resolves.toBe(fallback);
    await expect(resolveScreenshot()).resolves.toBeUndefined();
  });
  /* eslint-enable @typescript-eslint/no-explicit-any */
});

describe("heldFor", () => {
  const held = (bytes: ArrayBuffer) => ({
    id: "1:a",
    kind: "save" as const,
    romId: 1,
    romName: "Game",
    bytes,
    screenshotBytes: new Uint8Array([9, 9]).buffer,
    capturedAt: 0,
  });

  it("hands back the row holding these exact bytes", () => {
    const row = held(new Uint8Array([1, 2, 3]).buffer);

    expect(heldFor(row, new Uint8Array([1, 2, 3]))).toBe(row);
  });

  // The game wrote again, so the row pictures a moment that has passed.
  it("lets go once the save has moved on", () => {
    const row = held(new Uint8Array([1, 2, 3]).buffer);

    expect(heldFor(row, new Uint8Array([1, 2, 4]))).toBeNull();
  });

  it("has nothing to offer when nothing is held", () => {
    expect(heldFor(null, new Uint8Array([1]))).toBeNull();
  });
});

describe("saveState", () => {
  const bytes = new Uint8Array([1, 2, 3]).buffer;
  let rom: DetailedRom;

  beforeEach(() => {
    rom = {
      id: 1,
      fs_name_no_ext: "game",
      user_states: [],
    } as unknown as DetailedRom;
    stateApiMocks.uploadStates.mockReset();
    stateApiMocks.uploadStates.mockResolvedValue([
      { status: "fulfilled", value: { id: 7 } as StateSchema },
    ]);
    pendingAssetMocks.write.mockReset().mockResolvedValue(undefined);
    pendingAssetMocks.clear.mockReset().mockResolvedValue(undefined);
  });

  it("uploads the screenshot named after the state", async () => {
    await saveState({ rom, stateFile: bytes, screenshotFile: bytes });

    const { statesToUpload } = stateApiMocks.uploadStates.mock.calls[0][0];
    expect(statesToUpload[0].screenshotFile.name).toMatch(/^game \[.*\]\.png$/);
    expect(rom.user_states).toEqual([{ id: 7 }]);
  });

  it("still uploads the state when there is no screenshot", async () => {
    await saveState({ rom, stateFile: bytes });

    const { statesToUpload } = stateApiMocks.uploadStates.mock.calls[0][0];
    expect(statesToUpload[0].screenshotFile).toBeUndefined();
  });

  it("holds the state in the browser until the server takes it", async () => {
    await saveState({ rom, stateFile: bytes, screenshotFile: bytes });

    const held = pendingAssetMocks.write.mock.calls[0][0];
    expect(held).toMatchObject({
      kind: "state",
      romId: 1,
      romName: "game",
      bytes,
      screenshotBytes: bytes,
    });
    expect(pendingAssetMocks.clear).toHaveBeenCalledWith(held.id);
  });

  it("keeps a state the server refused", async () => {
    stateApiMocks.uploadStates.mockResolvedValue([
      { status: "rejected", reason: new Error("offline") },
    ]);

    await expect(saveState({ rom, stateFile: bytes })).resolves.toBeNull();

    expect(pendingAssetMocks.write).toHaveBeenCalledTimes(1);
    expect(pendingAssetMocks.clear).not.toHaveBeenCalled();
  });

  // The name pins the moment of the capture, so a retry updates the row the
  // first attempt opened instead of leaving a second copy behind.
  it("names the state after the moment it was captured", async () => {
    await saveState({ rom, stateFile: bytes });

    const { capturedAt } = pendingAssetMocks.write.mock.calls[0][0];
    const { statesToUpload } = stateApiMocks.uploadStates.mock.calls[0][0];
    expect(statesToUpload[0].stateFile.name).toMatch(
      /^game \[\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}-\d{3}\]\.state$/,
    );
    expect(statesToUpload[0].stateFile.name).toBe(
      `${sessionStateName(rom, new Date(capturedAt))}.state`,
    );
  });
});

describe("saveSaveOnUnload", () => {
  const rom = { id: 1, fs_name_no_ext: "game " } as unknown as DetailedRom;
  const bytes = new Uint8Array([1, 2, 3]).buffer;

  beforeEach(() => {
    saveApiMocks.sendSaveOnUnload.mockReset().mockReturnValue(true);
  });

  it("opens a capped autosave version named after the rom", () => {
    expect(saveSaveOnUnload({ rom, save: null, saveFile: bytes })).toBe(true);

    const request = saveApiMocks.sendSaveOnUnload.mock.calls[0][0];
    expect(request).toMatchObject({
      save: null,
      slot: "autosave",
      autocleanup: true,
    });
    expect(request.saveFile.name).toBe("game.srm");
  });

  it("updates the session's version under its own name", () => {
    const save = {
      id: 3,
      file_name: "a.srm",
      slot: "main_quest",
    } as SaveSchema;

    saveSaveOnUnload({ rom, save, saveFile: bytes, slot: "main_quest" });

    const request = saveApiMocks.sendSaveOnUnload.mock.calls[0][0];
    expect(request).toMatchObject({
      save,
      slot: "main_quest",
      autocleanup: false,
    });
    expect(request.saveFile.name).toBe("a.srm");
  });
});

describe("buildStateFormData", () => {
  const bytes = new Uint8Array([1, 2, 3]).buffer;

  it("adds the screenshot part only when there is a picture", () => {
    expect(
      buildStateFormData(bytes, bytes).get("screenshotFile"),
    ).toBeInstanceOf(Blob);
    expect(buildStateFormData(bytes).get("screenshotFile")).toBeNull();
    expect(buildStateFormData(bytes).get("stateFile")).toBeInstanceOf(Blob);
  });
});

describe("saveSave", () => {
  const save = { id: 3, file_name: "a.srm", slot: "main_quest" } as SaveSchema;
  const updated = { ...save, file_size_bytes: 4 } as SaveSchema;
  const bytes = new Uint8Array([1, 2, 3]).buffer;
  let rom: DetailedRom;

  beforeEach(() => {
    rom = {
      id: 1,
      fs_name_no_ext: "game",
      user_saves: [],
    } as unknown as DetailedRom;
    saveApiMocks.uploadSaves.mockReset();
    saveApiMocks.updateSave.mockReset();
    saveApiMocks.uploadSaves.mockResolvedValue([
      { status: "fulfilled", value: { id: 2, slot: "autosave" } },
    ]);
    saveApiMocks.updateSave.mockResolvedValue({ data: updated });
  });

  it("updates the version this session already created", async () => {
    rom.user_saves.push(save);

    await saveSave({ rom, save, saveFile: bytes, slot: "main_quest" });

    expect(saveApiMocks.updateSave).toHaveBeenCalledOnce();
    expect(saveApiMocks.uploadSaves).not.toHaveBeenCalled();
    expect(rom.user_saves).toEqual([updated]);
  });

  it("names a first screenshot after the version it updates", async () => {
    const shot = new Uint8Array([9]).buffer;
    const versioned = { ...save, file_name_no_ext: "a [t]" } as SaveSchema;

    await saveSave({
      rom,
      save: versioned,
      saveFile: bytes,
      screenshotFile: shot,
    });

    const { screenshotFile } = saveApiMocks.updateSave.mock.calls[0][0];
    expect(screenshotFile.name).toBe("a [t].png");
  });

  it("lists an updated version the rom did not know about", async () => {
    await saveSave({ rom, save, saveFile: bytes, slot: "main_quest" });

    expect(rom.user_saves).toEqual([updated]);
  });

  it("opens a capped autosave version when the session has none", async () => {
    await saveSave({ rom, save: null, saveFile: bytes });

    expect(saveApiMocks.uploadSaves).toHaveBeenCalledWith(
      expect.objectContaining({
        slot: "autosave",
        autocleanup: true,
        overwrite: true,
      }),
    );
    expect(rom.user_saves).toEqual([{ id: 2, slot: "autosave" }]);
  });

  it("leaves the datetime tag of a slotted upload to the backend", async () => {
    await saveSave({ rom, save: null, saveFile: bytes });

    const { savesToUpload } = saveApiMocks.uploadSaves.mock.calls[0][0];
    expect(savesToUpload[0].saveFile.name).toBe("game.srm");
  });

  it("keeps every version in a named slot", async () => {
    await saveSave({ rom, save: null, saveFile: bytes, slot: "speedrun" });

    expect(saveApiMocks.updateSave).not.toHaveBeenCalled();
    expect(saveApiMocks.uploadSaves).toHaveBeenCalledWith(
      expect.objectContaining({ slot: "speedrun", autocleanup: false }),
    );
  });
});
