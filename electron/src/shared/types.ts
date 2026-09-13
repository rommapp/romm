// The contract between the renderer (RomM's web frontend), the preload bridge
// and the main process. Kept free of Electron and Node imports so the frontend
// can depend on these shapes without pulling the shell into its bundle.

/** Why a launch could not be started. The renderer maps these to messages. */
export type LaunchErrorCode =
  | "unsupported-platform"
  | "no-emulator-configured"
  | "emulator-not-found"
  | "download-failed"
  | "already-running"
  | "invalid-request"
  | "launch-failed";

export class LaunchError extends Error {
  code: LaunchErrorCode;

  constructor(code: LaunchErrorCode, message: string) {
    super(message);
    this.name = "LaunchError";
    this.code = code;
  }
}

/** A launch as the renderer asks for it: it names the game and its candidate
 *  cores, never an executable. The main process resolves the emulator. */
export interface LaunchRequest {
  romId: number;
  /** Server-relative download path, as built by the frontend's getDownloadPath. */
  downloadPath: string;
  /** Used to name the cached file, never used as a path on its own. */
  fileName: string;
  platformSlug: string;
  /** Candidate libretro core names from the frontend's platform/core map. */
  cores: string[];
  /** Display name, used for window titles and logs. */
  name?: string;
}

export type LaunchStatus = "downloading" | "running" | "exited" | "failed";

export interface LaunchState {
  romId: number;
  status: LaunchStatus;
  /** 0..1 while downloading, absent otherwise. */
  progress?: number;
  /** Set when status is "failed". */
  error?: { code: LaunchErrorCode; message: string };
  /** Process exit code, set when status is "exited". */
  exitCode?: number | null;
}

export interface LaunchResult {
  romId: number;
  /** The emulator that was started, for display in the renderer. */
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
  /** Set when unsupported, so the renderer can explain why. */
  reason?: Extract<
    LaunchErrorCode,
    "unsupported-platform" | "no-emulator-configured" | "emulator-not-found"
  >;
}

/**
 * One row of the user's emulator table. `platformSlug` of "*" is the fallback
 * used for any platform without its own row.
 */
export interface EmulatorMapping {
  platformSlug: string;
  /** Absolute path to the emulator executable. */
  command: string;
  /** Argument template: "{rom}" becomes the cached ROM path, "{core}" the
   *  resolved core path. Substituted per argv entry, so no shell is involved. */
  args: string[];
  /** Display name for the emulator, shown in the renderer. */
  label?: string;
}

export interface DesktopConfig {
  /** Origin of the RomM server this shell is bound to, e.g. https://romm.lan. */
  serverUrl: string | null;
  /** Absolute path to the RetroArch executable, when the user has one. */
  retroarchPath: string | null;
  /** Directory holding RetroArch's libretro cores. */
  retroarchCoresPath: string | null;
  /** Per-platform overrides, consulted before the RetroArch default. */
  emulators: EmulatorMapping[];
  /** Where downloaded ROMs are cached. Defaults to userData/rom-cache. */
  cachePath: string | null;
  /** Upper bound on the ROM cache before least-recently-used eviction. */
  cacheLimitBytes: number;
  /** Trusted certificate fingerprints for self-signed servers. */
  trustedCertificates: string[];
}

export const DEFAULT_CACHE_LIMIT_BYTES = 20 * 1024 * 1024 * 1024;

/** The API the preload bridge exposes to the renderer as window.rommNative. */
export interface RommNativeBridge {
  readonly shellVersion: string;
  readonly os: "darwin" | "win32" | "linux";
  launch(request: LaunchRequest): Promise<LaunchResult>;
  cancel(romId: number): Promise<void>;
  getPlatformSupport(query: PlatformSupportQuery): Promise<PlatformSupport>;
  /** Subscribe to launch progress. Returns an unsubscribe function. */
  onLaunchState(listener: (state: LaunchState) => void): () => void;
  openSettings(): Promise<void>;
}
