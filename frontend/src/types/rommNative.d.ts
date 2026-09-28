// The `window.rommNative` bridge the RomM desktop shell injects into the page
// it loads, so the server's own frontend can launch a ROM in a locally
// installed emulator.
//
// Vendored: the canonical definition is `src/shared/types.ts` in
// rommapp/romm-desktop, which owns the contract. Keep the names and shapes
// identical to it so the two can be diffed. A stale copy here stays safe
// because `services/native.ts` feature-detects every call at runtime.

/** Why a launch could not be started. */
export type LaunchErrorCode =
  | "unsupported-platform"
  | "no-emulator-configured"
  | "emulator-not-found"
  | "download-failed"
  | "already-running"
  | "invalid-request"
  | "launch-failed";

/** A launch as the renderer asks for it: it names the game and its candidate
 *  cores, never an executable. The shell resolves the emulator itself. */
export interface LaunchRequest {
  romId: number;
  /** Server-relative download path, as built by `getDownloadPath`. */
  downloadPath: string;
  /** Used to name the cached file, never used as a path on its own. */
  fileName: string;
  platformSlug: string;
  /** Candidate libretro core names from the platform/core map. */
  cores: string[];
  /** Display name, used for window titles and logs. */
  name?: string;
  /** The ROM's path relative to the server's library root, as `full_path`
   *  reports it. Only ever joined onto the user's own library root, so a
   *  server on the same machine launches the file where it already is. */
  serverPath?: string;
  /** Size in bytes as the server reports it, checked against the local file
   *  before it stands in for a download. */
  fileSize?: number;
  /** Start the emulator fullscreen, so the play page's own choice covers both
   *  routes. Only a shell advertising `launch-fullscreen` acts on it, and only
   *  on its built-in RetroArch path; a configured emulator decides it in the
   *  arguments its owner wrote. */
  fullscreen?: boolean;
  /** Which of a multi-disc rom's files to boot, as the page's disc selector
   *  asks it: a rom file's id, or `"all"` for the whole set. Only a shell
   *  advertising `disc-choice` acts on it; one without always boots the set
   *  whole, which is where it was before the page could ask. */
  disc?: number | "all";
}

export type LaunchStatus =
  | "downloading"
  | "running"
  | "exited"
  | "failed"
  /** A save moved, after the emulator had already exited. Its own status rather
   *  than a stage, because it outlives the launch it belongs to: the exit is
   *  reported immediately and the upload settles afterwards. */
  | "sync";

/** What happened to a save around one launch. */
export type SaveSyncAction =
  /** The server's copy was written over the local one before the emulator ran. */
  | "downloaded"
  /** What the emulator wrote was sent to the save's slot. */
  | "uploaded"
  /** Nothing was replaced. The local bytes were kept as an archival save
   *  because the slot held progress this device had not seen. */
  | "archived"
  /** It was tried and did not work. The local file is untouched. */
  | "failed";

export interface SaveSyncOutcome {
  action: SaveSyncAction;
  /** The slot the save moved through, absent for an archival save, which
   *  deliberately sits outside every slot. */
  slot?: string | null;
  /** Why, when the outcome was a failure. For logs, not for display: the
   *  action has a message of its own. */
  detail?: string;
}

export interface LaunchState {
  romId: number;
  status: LaunchStatus;
  /** What is being fetched while downloading. Absent means the ROM.
   *  "emulator" covers both fetching a standalone emulator and the wait while
   *  the user installs it, which has no progress to report. "save" is the save
   *  pull, after the ROM is ready and before the emulator starts, and "state"
   *  is the savestate restore, just before it does. */
  stage?: "rom" | "core" | "emulator" | "firmware" | "save" | "state";
  /** The core being installed, while stage is "core". */
  core?: string;
  /** The firmware file being fetched, while stage is "firmware". Its own field
   *  rather than borrowing `core`, so neither has to be read as the other. */
  firmware?: string;
  /** The file being fetched out of a multi-disc set, and its place in that set,
   *  so a transfer per disc is not read as one restarting at 0%. Not every file
   *  is a disc of its own: a sheet's tracks are fetched with it. */
  file?: string;
  fileIndex?: number;
  fileCount?: number;
  /** The emulator being set up, while stage is "emulator". */
  emulator?: string;
  /** 0..1 while downloading, absent otherwise. */
  progress?: number;
  /** Bytes transferred so far, while downloading. */
  received?: number;
  /** Total bytes, when the server declared a length. */
  total?: number;
  /** Smoothed transfer rate, once there are two samples to compare. */
  bytesPerSecond?: number;
  /** Set when status is "failed". */
  error?: { code: LaunchErrorCode; message: string };
  /** Process exit code, set when status is "exited". */
  exitCode?: number | null;
  /** What happened to a save, set when status is "sync". */
  sync?: SaveSyncOutcome;
}

export interface LaunchResult {
  romId: number;
  /** The emulator that was started, for display. */
  emulator: string;
}

/** Asks whether a platform can be launched, given the cores it supports. */
export interface PlatformSupportQuery {
  platformSlug: string;
  cores: string[];
}

/** Whether a given platform can be launched natively, and by what. */
export interface PlatformSupport {
  supported: boolean;
  /** Human-readable emulator name when supported. */
  emulator?: string;
  /** Set when unsupported, so the reason can be explained. */
  reason?: Extract<
    LaunchErrorCode,
    "unsupported-platform" | "no-emulator-configured" | "emulator-not-found"
  >;
  /** The resolver's own message for the unsupported case, naming the paths it
   *  looked at. English only, so it belongs in a log rather than in the UI. */
  detail?: string;
}

/** Behaviour the presence of a method cannot express: a `LaunchRequest` field
 *  the shell honours, a `LaunchState` field it populates, a change to what an
 *  existing method does, advertised on the bridge's `capabilities`. */
export type ShellCapability =
  | "launch-stage"
  | "library-passthrough"
  | "platform-support-all"
  | "firmware-mirror"
  | "multi-disc"
  /** Saves are moved between the server and the emulator around a native
   *  launch. Save states are a separate setting, and a shell without this
   *  leaves both sides of it undone. */
  | "save-sync"
  /** Save states travel both ways: the ones RomM holds for the emulator a
   *  launch runs are restored into their slots before it starts, reported as
   *  the "state" stage, and the ones the run writes go up after it exits. A
   *  shell without this only sends them. */
  | "state-restore"
  /** `LaunchRequest.disc` is honoured, so the page's disc selector covers a
   *  native launch too: one disc of a set is fetched and booted on its own. */
  | "disc-choice"
  /** `LaunchRequest.fullscreen` is honoured, so the page's own full-screen
   *  choice covers a native launch as well as the in-browser one. */
  | "launch-fullscreen";

export interface RommNativeBridge {
  readonly shellVersion: string;
  readonly os: "darwin" | "win32" | "linux";
  /** Plain strings rather than `ShellCapability`, so a newer shell's entries
   *  are readable here without being a type error. */
  readonly capabilities: readonly string[];
  launch(request: LaunchRequest): Promise<LaunchResult>;
  cancel(romId: number): Promise<void>;
  getPlatformSupport(query: PlatformSupportQuery): Promise<PlatformSupport>;
  getPlatformSupportAll(
    queries: PlatformSupportQuery[],
  ): Promise<Record<string, PlatformSupport>>;
  /** Subscribe to launch progress. Returns an unsubscribe function. */
  onLaunchState(listener: (state: LaunchState) => void): () => void;
  openSettings(): Promise<void>;
}

declare global {
  interface Window {
    rommNative?: RommNativeBridge;
  }
}
