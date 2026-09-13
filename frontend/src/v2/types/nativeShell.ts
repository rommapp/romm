// Mirrors `RommNativeBridge` in electron/src/shared/types.ts, which is the
// authority for this contract: the desktop shell injects it as
// `window.rommNative`. Only the members the web app actually calls are
// declared here, so the shell can grow without touching the frontend.

/** Why a native launch could not be started. */
export type NativeLaunchErrorCode =
  | "unsupported-platform"
  | "no-emulator-configured"
  | "emulator-not-found"
  | "download-failed"
  | "already-running"
  | "invalid-request"
  | "launch-failed";

export type NativeLaunchStatus =
  "downloading" | "running" | "exited" | "failed";

export interface NativeLaunchState {
  romId: number;
  status: NativeLaunchStatus;
  /** 0..1 while downloading, absent otherwise. */
  progress?: number;
  error?: { code: NativeLaunchErrorCode; message: string };
  exitCode?: number | null;
}

export interface NativeLaunchRequest {
  romId: number;
  downloadPath: string;
  fileName: string;
  platformSlug: string;
  /** Candidate libretro cores, from the shared platform/core map. */
  cores: string[];
  name?: string;
}

export interface NativeLaunchResult {
  romId: number;
  /** The emulator that was started, for display. */
  emulator: string;
}

export interface NativePlatformSupport {
  supported: boolean;
  emulator?: string;
  reason?: Extract<
    NativeLaunchErrorCode,
    "unsupported-platform" | "no-emulator-configured" | "emulator-not-found"
  >;
}

export interface NativeShellBridge {
  readonly shellVersion: string;
  readonly os: "darwin" | "win32" | "linux";
  launch(request: NativeLaunchRequest): Promise<NativeLaunchResult>;
  cancel(romId: number): Promise<void>;
  getPlatformSupport(query: {
    platformSlug: string;
    cores: string[];
  }): Promise<NativePlatformSupport>;
  /** Subscribe to launch progress. Returns an unsubscribe function. */
  onLaunchState(listener: (state: NativeLaunchState) => void): () => void;
  openSettings(): Promise<void>;
}

declare global {
  interface Window {
    /** Present only when RomM is running inside the desktop shell. */
    rommNative?: NativeShellBridge;
  }
}
