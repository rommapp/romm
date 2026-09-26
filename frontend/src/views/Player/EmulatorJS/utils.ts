import Bowser from "bowser";
import {
  type Body_add_state_api_states_post as AddStateInput,
  type SaveSchema,
  type StateSchema,
} from "@/__generated__";
import saveApi, {
  AUTOSAVE_SLOT,
  sessionSaveFile,
  sessionScreenshotFile,
} from "@/services/api/save";
import stateApi, { sessionStateFiles } from "@/services/api/state";
import pendingAssetStore, {
  pendingAssetId,
  type PendingAsset,
} from "@/services/pending-asset";
import storeHeartbeat from "@/stores/heartbeat";
import { type DetailedRom } from "@/stores/roms";
import { buildFormInput } from "@/utils/formData";

/** Tears the emulator down once, however many owners ask. */
export function exitEmulatorOnce() {
  // The player and its shell both unmount on the way out, and a second exit
  // throws ErrnoError(28) unmounting the filesystem, then aborts the runtime.
  const emulator = window.EJS_emulator;
  if (!emulator || emulator.__rommExited) return;
  emulator.__rommExited = true;
  emulator.callEvent("exit");
}

// Long enough for any core to hand over a frame.
const SCREENSHOT_TIMEOUT_MS = 3000;

// A capture deletes the file the previous one still polls for, and that poll
// never gives up, so captures are taken one at a time.
let capturing: Promise<ArrayBuffer | undefined> = Promise.resolve(undefined);

// EmulatorJS 4.2.3 hands `EJS_onSaveState` no screenshot and its own capture
// renders a slice of the frame, so pictures are read off the live canvas.
export function captureScreenshot(): Promise<ArrayBuffer | undefined> {
  capturing = capturing.catch(() => undefined).then(takeScreenshot);
  return capturing;
}

async function takeScreenshot(): Promise<ArrayBuffer | undefined> {
  const gameManager = window.EJS_emulator?.gameManager;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const screenshot = await Promise.race([
      gameManager?.screenshot(),
      new Promise<undefined>((resolve) => {
        timer = setTimeout(() => resolve(undefined), SCREENSHOT_TIMEOUT_MS);
      }),
    ]);
    // An empty buffer is a failed readback, not a picture.
    if (screenshot?.byteLength) return screenshot;
  } catch (error) {
    console.error("Failed to capture a screenshot", error);
  } finally {
    clearTimeout(timer);
  }
  releaseScreenshotWait(gameManager);
  return undefined;
}

// The poll behind a capture that never arrived runs for the rest of the
// session; the file it is waiting for is what stops it.
function releaseScreenshotWait(gameManager?: {
  FS?: { writeFile(path: string, data: Uint8Array): void };
}) {
  try {
    gameManager?.FS?.writeFile("/screenshot.png", new Uint8Array(0));
  } catch (error) {
    console.error("Failed to release a stuck screenshot capture", error);
  }
}

/**
 * The SRAM as the core holds it right now.
 *
 * Returns:
 *   The bytes, or null when the core has written no save file.
 */
export function dumpSaveFile(): Uint8Array | null {
  // Passing true flushes the core's memory into the file this reads: the copy
  // already on the emulator's filesystem predates a state it just restored.
  return window.EJS_emulator?.gameManager?.getSaveFile(true) ?? null;
}

/** The picture for a save or a state: the live canvas, else EmulatorJS'. */
export async function resolveScreenshot(
  emulatorScreenshot?: ArrayBuffer,
): Promise<ArrayBuffer | undefined> {
  return (await captureScreenshot()) ?? emulatorScreenshot;
}

/**
 * The held row, when it holds these exact bytes.
 *
 * Returns:
 *   The row, or null when there is none or the bytes have moved on since.
 */
export function heldFor(
  pending: PendingAsset | null,
  bytes: Uint8Array,
): PendingAsset | null {
  return pending && bytesEqual(new Uint8Array(pending.bytes), bytes)
    ? pending
    : null;
}

/** Console-mode state upload; without a picture there is no screenshot part. */
export function buildStateFormData(
  stateFile: ArrayBuffer,
  screenshotFile?: ArrayBuffer,
): FormData {
  return buildFormInput<AddStateInput>([
    ["stateFile", new Blob([stateFile]), "state.save"],
    [
      "screenshotFile",
      screenshotFile
        ? new Blob([screenshotFile], { type: "image/png" })
        : undefined,
      "screenshot.png",
    ],
  ]);
}

/** A state upload's outcome: taken, or held in this browser for later, or neither. */
export interface StateUpload {
  state: StateSchema | null;
  kept: boolean;
}

export async function saveState({
  rom,
  stateFile,
  screenshotFile,
}: {
  rom: DetailedRom;
  stateFile: ArrayBuffer;
  screenshotFile?: ArrayBuffer;
}): Promise<StateUpload> {
  // A zero-length buffer means the core failed to serialize its state (a torn
  // read from a running threaded core). Refuse to upload it so a broken
  // capture can't overwrite the user's good states on the server.
  if (stateFile.byteLength === 0) {
    console.error("Refusing to upload empty state file");
    return { state: null, kept: false };
  }

  const capturedAt = new Date();
  // Held in the browser until the server takes it, so a state captured offline
  // reaches it on a later pass.
  const pendingId = pendingAssetId(rom.id);
  const kept = await pendingAssetStore.write({
    id: pendingId,
    kind: "state",
    romId: rom.id,
    romName: rom.name ?? rom.fs_name_no_ext,
    fsNameNoExt: rom.fs_name_no_ext,
    cover: rom.path_cover_small,
    bytes: stateFile,
    screenshotBytes: screenshotFile,
    emulator: window.EJS_core,
    capturedAt: capturedAt.getTime(),
  });
  // Nothing gets through while the server is down; the held state goes once
  // it is back.
  if (!storeHeartbeat().connected) return { state: null, kept };

  try {
    const uploadedStates = await stateApi.uploadStates({
      rom: rom,
      emulator: window.EJS_core,
      statesToUpload: [
        sessionStateFiles(rom, capturedAt, stateFile, screenshotFile),
      ],
    });

    const uploadedState = uploadedStates[0];
    if (uploadedState.status == "fulfilled") {
      await pendingAssetStore.clear(pendingId);
      if (rom) rom.user_states.unshift(uploadedState.value);
      return { state: uploadedState.value, kept: false };
    }
  } catch (error) {
    console.error("Failed to upload state", error);
  }

  return { state: null, kept };
}

// `save` is the version this session already created: it is updated in place,
// while a null `save` opens a new version in `slot`.
export async function saveSave({
  rom,
  save,
  saveFile,
  screenshotFile,
  deviceId,
  slot = AUTOSAVE_SLOT,
}: {
  rom: DetailedRom;
  save: SaveSchema | null;
  saveFile: ArrayBuffer;
  screenshotFile?: ArrayBuffer;
  deviceId?: string;
  slot?: string;
}): Promise<SaveSchema | null> {
  if (save) {
    try {
      const { data: updatedSave } = await saveApi.updateSave({
        save: save,
        saveFile: sessionSaveFile(rom, save, saveFile),
        screenshotFile: screenshotFile
          ? sessionScreenshotFile(rom, save, screenshotFile)
          : undefined,
        deviceId,
      });

      const index = rom.user_saves.findIndex((s) => s.id === updatedSave.id);
      if (index === -1) rom.user_saves.unshift(updatedSave);
      else rom.user_saves[index] = updatedSave;

      return updatedSave;
    } catch (error) {
      console.error("Failed to update save", error);
      return null;
    }
  }

  // The backend timestamps slotted uploads, tagging save and screenshot alike.
  try {
    const uploadedSaves = await saveApi.uploadSaves({
      rom: rom,
      emulator: window.EJS_core,
      deviceId,
      slot,
      // Like Argosy: the autosave slot keeps a capped history, named slots
      // keep every version.
      autocleanup: slot === AUTOSAVE_SLOT,
      // The boot source is an explicit choice on the launch screen, so neither
      // the stale-device guard nor the hash dedupe applies (callers skip dupes).
      overwrite: true,
      savesToUpload: [
        {
          saveFile: sessionSaveFile(rom, null, saveFile),
          screenshotFile: screenshotFile
            ? sessionScreenshotFile(rom, null, screenshotFile)
            : undefined,
        },
      ],
    });

    const uploadedSave = uploadedSaves[0];
    if (uploadedSave.status == "fulfilled") {
      if (rom) rom.user_saves.unshift(uploadedSave.value);
      return uploadedSave.value;
    }
  } catch (error) {
    console.error("Failed to upload save", error);
  }

  return null;
}

// The unload counterpart of saveSave: nothing awaits it, so the rom's list is
// left alone. False when the save is too big for a keepalive body.
export function saveSaveOnUnload({
  rom,
  save,
  saveFile,
  deviceId,
  slot = AUTOSAVE_SLOT,
}: {
  rom: DetailedRom;
  save: SaveSchema | null;
  saveFile: ArrayBuffer;
  deviceId?: string;
  slot?: string;
}): boolean {
  return saveApi.sendSaveOnUnload({
    rom,
    save,
    saveFile: sessionSaveFile(rom, save, saveFile),
    emulator: window.EJS_core,
    deviceId,
    slot,
    autocleanup: slot === AUTOSAVE_SLOT,
  });
}

// Per EmulatorJS "saveSaveFiles" tick, whether the SRAM is worth uploading
// (#4201). Two agreeing ticks keep a mid-write save from being uploaded (#2349).
export function createSaveSyncTracker() {
  let lastUploaded: Uint8Array | null = null;
  let baseline: Uint8Array | null = null;
  let previousTick: Uint8Array | null = null;
  // Bytes the server does not hold: neither the last upload nor the SRAM the
  // session started from.
  const hasChanges = (save: Uint8Array): boolean =>
    !bytesEqual(save, lastUploaded) && !bytesEqual(save, baseline);
  return {
    // Bytes downloaded from the server: neither the tick nor a forced write
    // needs to send them back.
    seed(save: Uint8Array | null) {
      lastUploaded = save;
      baseline = save;
      previousTick = save;
    },
    // SRAM restored by a state or a fresh boot: the tick waits for a change,
    // but a forced write still persists it since the server has no copy.
    baseline(save: Uint8Array | null) {
      lastUploaded = null;
      baseline = save;
      previousTick = save;
    },
    shouldUpload(save: Uint8Array): boolean {
      const stable = bytesEqual(save, previousTick);
      previousTick = save;
      return stable && hasChanges(save);
    },
    // Leaving the player cannot wait for a second tick, so it uploads on
    // this alone.
    hasChanges,
    markUploaded(save: Uint8Array) {
      lastUploaded = save;
      baseline = null;
    },
    // Whether the server already holds these exact bytes.
    isUploaded(save: Uint8Array): boolean {
      return bytesEqual(save, lastUploaded);
    },
  };
}

// The tick re-offers a failed upload every second, which only hammers a server
// that is refusing it or on its way down.
export const RETRY_BACKOFF_MIN_MS = 2_000;
export const RETRY_BACKOFF_MAX_MS = 30_000;

/** Spaces out the retries of a failing upload, doubling the wait up to a cap. */
export function createRetryBackoff(now: () => number = Date.now) {
  let delay = 0;
  let retryAt = 0;
  return {
    ready: (): boolean => now() >= retryAt,
    failed() {
      delay = Math.min(
        Math.max(delay * 2, RETRY_BACKOFF_MIN_MS),
        RETRY_BACKOFF_MAX_MS,
      );
      retryAt = now() + delay;
    },
    reset() {
      delay = 0;
      retryAt = 0;
    },
  };
}

// EmulatorJS reads each tick off the FS into a fresh buffer, so the tracker can
// hold on to one rather than fingerprint it.
export function bytesEqual(
  a: Uint8Array | null,
  b: Uint8Array | null,
): boolean {
  if (!a || !b) return a === b;
  if (a.byteLength !== b.byteLength) return false;
  for (let i = 0; i < a.byteLength; i++) if (a[i] !== b[i]) return false;
  return true;
}

// The core exposes no write hook for its SRAM and EmulatorJS flushes it only on
// its "System Save interval" (5 minutes by default), so polling it every second
// is what gets an in-game save to the server right after the game writes it.
export const SAVE_SYNC_POLL_MS = 1000;
// Each tick copies and compares the whole SRAM, so the interval grows with it
// past 1 MB (1 ms of work per second either way) rather than hitching big saves.
const SAVE_SYNC_BYTES_PER_MS = 1024;

interface PollableEmulator {
  started: boolean;
  gameManager: {
    saveSaveFiles(): void;
    getSaveFile(save: boolean): Uint8Array | null;
  };
}

/**
 * Flushes the SRAM on a timer while the game runs, firing EmulatorJS'
 * "saveSaveFiles" tick.
 *
 * Returns:
 *   A function that stops the timer.
 */
export function pollSaveFiles(emulator: PollableEmulator): () => void {
  const sramBytes = emulator.gameManager.getSaveFile(false)?.byteLength ?? 0;
  const timer = setInterval(
    () => {
      if (emulator.started) emulator.gameManager.saveSaveFiles();
    },
    Math.max(SAVE_SYNC_POLL_MS, sramBytes / SAVE_SYNC_BYTES_PER_MS),
  );
  return () => clearInterval(timer);
}

// saveSave needs an ArrayBuffer, and a Uint8Array's own buffer may be shared or
// wider than the view, so hand it a standalone copy.
export function toArrayBuffer(view: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(view.byteLength);
  copy.set(view);
  return copy.buffer;
}

export function loadEmulatorJSSave(save: Uint8Array) {
  const FS = window.EJS_emulator.gameManager.FS;
  const path = window.EJS_emulator.gameManager.getSaveFilePath();
  const paths = path.split("/");
  let cp = "";
  for (let i = 0; i < paths.length - 1; i++) {
    if (paths[i] === "") continue;
    cp += "/" + paths[i];
    if (!FS.analyzePath(cp).exists) FS.mkdir(cp);
  }
  if (FS.analyzePath(path).exists) FS.unlink(path);
  FS.writeFile(path, save);
  window.EJS_emulator.gameManager.loadSaveFiles();
}

export function loadEmulatorJSState(state: Uint8Array) {
  window.EJS_emulator.gameManager.loadState(state);
}

export function invalidateEmulatorJSRomCacheIfRenamed(rom: {
  id: number;
  fs_name: string;
}) {
  const fsNameStorageKey = `player:${rom.id}:fs_name`;
  const previousFsName = localStorage.getItem(fsNameStorageKey);

  if (previousFsName && previousFsName !== rom.fs_name) {
    window.indexedDB.deleteDatabase("EmulatorJS-roms");
  }

  localStorage.setItem(fsNameStorageKey, rom.fs_name);
}

// EmulatorJS drops the config.yaml defaults (EJS_defaultOptions) in two spots:
// - preGetSetting short-circuits to the saved-settings localStorage object
//   once ANY setting or control was changed, returning undefined for keys the
//   user never touched (webgl2Enabled, vsync, shader, ...).
// - getCoreSettings builds the RetroArch core options file, but returns ""
//   when localStorage is enabled and holds no saved entry yet, so on a fresh
//   launch core options (e.g. mupen64plus-FXAA) never reach the core.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function installDefaultOptionsFallback(emulator: any) {
  if (emulator.__rommSettingsPatched) return;
  emulator.__rommSettingsPatched = true;

  const originalPreGetSetting = emulator.preGetSetting.bind(emulator);
  emulator.preGetSetting = (setting: string) => {
    const value = originalPreGetSetting(setting);
    if (value !== undefined && value !== null) return value;
    const defaults = emulator.config?.defaultOptions ?? {};
    return defaults[setting] !== undefined ? defaults[setting] : null;
  };

  emulator.getCoreSettings = () => {
    const defaults: Record<string, unknown> =
      emulator.config?.defaultOptions ?? {};
    let saved: Record<string, unknown> = {};
    if (window.localStorage && !emulator.config?.disableLocalStorage) {
      try {
        const raw = localStorage.getItem(emulator.getLocalStorageKey());
        const parsed = raw ? JSON.parse(raw) : null;
        if (parsed?.settings instanceof Object) saved = parsed.settings;
      } catch (error) {
        console.warn("Could not load previous settings", error);
      }
    }
    const merged = { ...defaults, ...saved };
    let output = "";
    for (const key in merged) {
      const value = merged[key];
      // Match upstream formatting: numeric values unquoted, strings quoted.
      const formatted = Number.isNaN(Number(value)) ? `"${value}"` : value;
      output += `${key} = ${formatted}\n`;
    }
    return output;
  };

  // Recompute the values the constructor captured via the unpatched
  // preGetSetting. They are consumed after this point: rewindEnabled when
  // GameManager writes retroarch.cfg, webgl2Enabled when the core variant is
  // picked during download, videoRotation on the first resize.
  emulator.rewindEnabled =
    emulator.preGetSetting("rewindEnabled") === "enabled";
  if (![0, 1, 2, 3].includes(emulator.config?.videoRotation)) {
    emulator.videoRotation = emulator.preGetSetting("videoRotation") || 0;
  }
  const webgl2Setting = emulator.preGetSetting("webgl2Enabled");
  if (webgl2Setting === "disabled" || !emulator.supportsWebgl2) {
    emulator.webgl2Enabled = false;
  } else if (webgl2Setting === "enabled") {
    emulator.webgl2Enabled = true;
  } else {
    emulator.webgl2Enabled = null;
  }
}

// GamepadHandler polls once in its constructor, before EmulatorJS registers
// its "connected" listener, so a pad the page already sees (e.g. the one that
// pressed Play) is never assigned to a player until it reconnects.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function replayConnectedGamepads(emulator: any) {
  const handler = emulator.gamepad;
  if (emulator.__rommGamepadsReplayed || !handler?.dispatchEvent) return;
  emulator.__rommGamepadsReplayed = true;
  for (const pad of [...(handler.gamepads ?? [])]) {
    if (!pad) continue;
    try {
      handler.dispatchEvent("connected", { gamepadIndex: pad.index });
    } catch (error) {
      console.warn("Could not assign connected gamepad", error);
    }
  }
}

// Trap the window.EJS_emulator assignment so the instance is patched right
// after the constructor returns, before the async core download and boot
// consume any of the patched values. Patching later (e.g. in EJS_onGameStart)
// is too late: by then the GL context exists, retroarch.cfg and the core
// options file are written, and saved settings were already applied.
export function installEJSDefaultOptionsTrap() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let instance: any;
  Object.defineProperty(window, "EJS_emulator", {
    configurable: true,
    get: () => instance,
    set: (value) => {
      instance = value;
      if (!value) return;
      installDefaultOptionsFallback(value);
      replayConnectedGamepads(value);
    },
  });
}

const IOS_FULLSCREEN_NAV_SELECTOR =
  ".v-app-bar, .v-bottom-navigation, .v-navigation-drawer";
const IOS_FULLSCREEN_STYLE = `
  [data-ios-fullscreen-active] {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100svh !important;
    z-index: 99999 !important;
    background: #000 !important;
  }
  [data-ios-fullscreen-hidden] { display: none !important; }
`;

function isIOSFullscreenShimRequired() {
  const osName = Bowser.getParser(navigator.userAgent).getOSName(true);
  return (
    osName === "ios" ||
    // iPadOS 13+ reports as macOS with touch support, so fall back to that check.
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

export function installIOSFullscreenShim() {
  if (!isIOSFullscreenShimRequired()) {
    return () => {};
  }

  const proto = HTMLElement.prototype;
  const overrides: Array<{
    target: object;
    key: PropertyKey;
    prev?: PropertyDescriptor;
  }> = [];
  const override = (
    target: object,
    key: PropertyKey,
    descriptor: PropertyDescriptor,
  ) => {
    overrides.push({
      target,
      key,
      prev: Object.getOwnPropertyDescriptor(target, key),
    });
    Object.defineProperty(target, key, { configurable: true, ...descriptor });
  };

  const styleEl = document.createElement("style");
  styleEl.textContent = IOS_FULLSCREEN_STYLE;
  document.head.appendChild(styleEl);

  let fullscreenElement: HTMLElement | null = null;

  const dispatchChange = (target: HTMLElement) => {
    document.dispatchEvent(new Event("fullscreenchange"));
    target.dispatchEvent(new Event("fullscreenchange"));
  };

  const enter = (el: HTMLElement) => {
    if (fullscreenElement === el) return Promise.resolve();
    if (fullscreenElement) void exit();

    el.setAttribute("data-ios-fullscreen-active", "");
    document
      .querySelectorAll<HTMLElement>(IOS_FULLSCREEN_NAV_SELECTOR)
      .forEach((nav) => nav.setAttribute("data-ios-fullscreen-hidden", ""));
    fullscreenElement = el;
    dispatchChange(el);
    return Promise.resolve();
  };

  const exit = () => {
    const el = fullscreenElement;
    if (!el) return Promise.resolve();
    el.removeAttribute("data-ios-fullscreen-active");
    document
      .querySelectorAll<HTMLElement>("[data-ios-fullscreen-hidden]")
      .forEach((nav) => nav.removeAttribute("data-ios-fullscreen-hidden"));
    fullscreenElement = null;
    dispatchChange(el);
    return Promise.resolve();
  };

  override(document, "fullscreenEnabled", { get: () => true });
  override(document, "fullscreenElement", { get: () => fullscreenElement });
  override(document, "exitFullscreen", { value: exit, writable: true });
  override(proto, "requestFullscreen", {
    value: function (this: HTMLElement) {
      return enter(this);
    },
    writable: true,
  });
  override(proto, "webkitRequestFullscreen", {
    value: function (this: HTMLElement) {
      void enter(this);
    },
    writable: true,
  });

  return () => {
    void exit();
    styleEl.remove();
    while (overrides.length) {
      const { target, key, prev } = overrides.pop()!;
      if (prev) Object.defineProperty(target, key, prev);
      else Reflect.deleteProperty(target, key);
    }
  };
}

// EJS_Buttons cannot relabel the context menu button, so its text is set here.
export function labelContextMenuButton(label: string) {
  const text: HTMLElement | null | undefined =
    window.EJS_emulator?.elements?.bottomBar?.contextMenu?.[0]?.querySelector(
      ".ejs_menu_text",
    );
  if (text) text.innerText = label;
}

export function createQuickLoadButton(label: string): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "presentation");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("viewBox", "2 2 20 20");
  svg.innerHTML =
    '<path d="M12,7L17,12H14V16H10V12H7L12,7M19,21H5A2,2 0 0,1 3,19V5A2,2 0 0,1 5,3H19A2,2 0 0,1 21,5V19A2,2 0 0,1 19,21M19,19V5H5V19H19Z"></path>';
  const text = document.createElement("span");
  text.classList.add("ejs_menu_text");
  text.innerText = label;
  button.classList.add("ejs_menu_button");
  button.appendChild(svg);
  button.appendChild(text);

  const ejsMenuBar = document.querySelector("#game .ejs_menu_bar");
  const loadStateBtn = ejsMenuBar?.querySelector(
    ".ejs_menu_button:nth-child(5)",
  );
  if (ejsMenuBar && loadStateBtn) {
    ejsMenuBar.insertBefore(button, loadStateBtn);
  }

  return button;
}

export function createExitEmulationButton(label: string): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "presentation");
  svg.setAttribute("focusable", "false");
  svg.innerHTML =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 460"><path style="fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;stroke:rgb(255,255,255);stroke-opacity:1;stroke-miterlimit:4;" d="M 14.000061 7.636414 L 14.000061 4.5 C 14.000061 4.223877 13.776123 3.999939 13.5 3.999939 L 4.5 3.999939 C 4.223877 3.999939 3.999939 4.223877 3.999939 4.5 L 3.999939 19.5 C 3.999939 19.776123 4.223877 20.000061 4.5 20.000061 L 13.5 20.000061 C 13.776123 20.000061 14.000061 19.776123 14.000061 19.5 L 14.000061 16.363586 " transform="matrix(21.333333,0,0,21.333333,0,0)"></path><path style="fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;stroke:rgb(255,255,255);stroke-opacity:1;stroke-miterlimit:4;" d="M 9.999939 12 L 21 12 M 21 12 L 18.000366 8.499939 M 21 12 L 18 15.500061 " transform="matrix(21.333333,0,0,21.333333,0,0)"></path></svg>';
  const text = document.createElement("span");
  text.classList.add("ejs_menu_text", "ejs_menu_text_right");
  text.innerText = label;
  button.classList.add("ejs_menu_button");
  button.appendChild(svg);
  button.appendChild(text);

  const ejsMenuBar = document.querySelector("#game .ejs_menu_bar");
  ejsMenuBar?.appendChild(button);

  return button;
}

export function createSaveQuitButton(label: string): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "presentation");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("viewBox", "2 2 20 20");
  svg.innerHTML =
    '<path d="M17,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H11.81C11.42,20.34 11.17,19.6 11.07,18.84C9.5,18.31 8.66,16.6 9.2,15.03C9.61,13.83 10.73,13 12,13C12.44,13 12.88,13.1 13.28,13.29C15.57,11.5 18.83,11.59 21,13.54V7L17,3M15,9H5V5H15V9M13,17H17V14L22,18.5L17,23V20H13V17"></path>';
  const text = document.createElement("span");
  text.classList.add("ejs_menu_text", "ejs_menu_text_right");
  text.innerText = label;
  button.classList.add("ejs_menu_button");
  button.appendChild(svg);
  button.appendChild(text);

  const ejsMenuBar = document.querySelector("#game .ejs_menu_bar");
  ejsMenuBar?.appendChild(button);

  return button;
}
