import { type Session } from "electron";
import { type ChildProcess, spawn } from "node:child_process";
import {
  type LaunchRequest,
  type LaunchResult,
  type LaunchState,
  LaunchError,
  type PlatformSupport,
  type PlatformSupportQuery,
} from "../shared/types.ts";
import { loadConfig } from "./config.ts";
import { resolveLaunch } from "./emulator/resolve.ts";
import { ensureRom } from "./rom-cache.ts";

interface ActiveLaunch {
  controller: AbortController;
  child: ChildProcess | null;
}

function toLaunchError(error: unknown): LaunchError {
  if (error instanceof LaunchError) return error;
  const message = error instanceof Error ? error.message : String(error);
  return new LaunchError("launch-failed", message);
}

export class Launcher {
  private readonly active = new Map<number, ActiveLaunch>();
  private readonly emit: (state: LaunchState) => void;

  constructor(emit: (state: LaunchState) => void) {
    this.emit = emit;
  }

  /** Whether the platform would launch right now, without downloading anything. */
  async getPlatformSupport(
    query: PlatformSupportQuery,
  ): Promise<PlatformSupport> {
    const config = await loadConfig();
    try {
      const launch = resolveLaunch({
        config,
        platformSlug: query.platformSlug,
        cores: query.cores,
        // A probe never runs, so the ROM path only has to be non-empty.
        romPath: "",
      });
      return { supported: true, emulator: launch.label };
    } catch (error) {
      const launchError = toLaunchError(error);
      switch (launchError.code) {
        case "unsupported-platform":
        case "no-emulator-configured":
        case "emulator-not-found":
          return { supported: false, reason: launchError.code };
        default:
          return { supported: false, reason: "no-emulator-configured" };
      }
    }
  }

  async launch(
    request: LaunchRequest,
    session: Session,
  ): Promise<LaunchResult> {
    if (this.active.has(request.romId)) {
      throw new LaunchError(
        "already-running",
        `${request.name ?? "This game"} is already running.`,
      );
    }

    const controller = new AbortController();
    const entry: ActiveLaunch = { controller, child: null };
    this.active.set(request.romId, entry);

    try {
      const config = await loadConfig();

      // Resolve the emulator before downloading: a missing core should fail
      // immediately rather than after a multi-gigabyte transfer.
      resolveLaunch({
        config,
        platformSlug: request.platformSlug,
        cores: request.cores,
        romPath: "",
      });

      this.emit({ romId: request.romId, status: "downloading", progress: 0 });
      const rom = await ensureRom({
        config,
        session,
        romId: request.romId,
        fileName: request.fileName,
        downloadPath: request.downloadPath,
        signal: controller.signal,
        onProgress: (received, total) => {
          this.emit({
            romId: request.romId,
            status: "downloading",
            progress: total ? received / total : undefined,
          });
        },
      });

      const launch = resolveLaunch({
        config,
        platformSlug: request.platformSlug,
        cores: request.cores,
        romPath: rom.path,
      });

      // argv form, never a shell string, so a path containing shell
      // metacharacters stays a single argument.
      const child = spawn(launch.command, launch.args, {
        stdio: "ignore",
        windowsHide: false,
      });
      entry.child = child;

      child.on("error", (error) => {
        this.active.delete(request.romId);
        this.emit({
          romId: request.romId,
          status: "failed",
          error: { code: "launch-failed", message: error.message },
        });
      });

      child.on("exit", (code) => {
        this.active.delete(request.romId);
        this.emit({ romId: request.romId, status: "exited", exitCode: code });
      });

      this.emit({ romId: request.romId, status: "running" });
      return { romId: request.romId, emulator: launch.label };
    } catch (error) {
      this.active.delete(request.romId);
      const launchError = toLaunchError(error);
      this.emit({
        romId: request.romId,
        status: "failed",
        error: { code: launchError.code, message: launchError.message },
      });
      throw launchError;
    }
  }

  /** Abort an in-flight download. A running emulator is left alone. */
  cancel(romId: number): void {
    const entry = this.active.get(romId);
    if (!entry || entry.child) return;
    entry.controller.abort();
    this.active.delete(romId);
  }

  /** Stop tracking on shutdown so pending downloads do not outlive the window. */
  dispose(): void {
    for (const entry of this.active.values()) {
      if (!entry.child) entry.controller.abort();
    }
    this.active.clear();
  }
}
