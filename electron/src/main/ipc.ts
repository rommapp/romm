import { BrowserWindow, ipcMain, shell } from "electron";
import { LaunchError } from "../shared/types.ts";
import { loadConfig } from "./config.ts";
import { type Launcher } from "./launcher.ts";
import { validateLaunchRequest } from "./safety.ts";

const LAUNCH_STATE_CHANNEL = "romm:launch-state";

function asPlatformQuery(value: unknown): {
  platformSlug: string;
  cores: string[];
} {
  if (typeof value !== "object" || value === null) {
    throw new LaunchError("invalid-request", "Query must be an object.");
  }
  const candidate = value as Record<string, unknown>;
  const cores = candidate.cores;
  if (
    typeof candidate.platformSlug !== "string" ||
    !Array.isArray(cores) ||
    cores.some((core) => typeof core !== "string")
  ) {
    throw new LaunchError(
      "invalid-request",
      "Query must name a platform and its cores.",
    );
  }
  return { platformSlug: candidate.platformSlug, cores: cores as string[] };
}

export function registerIpc(launcher: Launcher): void {
  ipcMain.handle("romm:launch", async (event, raw: unknown) => {
    const request = validateLaunchRequest(raw);
    // The session comes from the calling window, never from the request, so a
    // launch always downloads with that window's own credentials.
    return launcher.launch(request, event.sender.session);
  });

  ipcMain.handle("romm:cancel", (_event, romId: unknown) => {
    if (typeof romId === "number" && Number.isInteger(romId)) {
      launcher.cancel(romId);
    }
  });

  ipcMain.handle("romm:platform-support", (_event, raw: unknown) =>
    launcher.getPlatformSupport(asPlatformQuery(raw)),
  );

  ipcMain.handle("romm:open-settings", async () => {
    const config = await loadConfig();
    if (config.cachePath) await shell.openPath(config.cachePath);
  });
}

/** Push launch progress to every open window. */
export function broadcastLaunchState(state: unknown): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (window.isDestroyed()) continue;
    window.webContents.send(LAUNCH_STATE_CHANNEL, state);
  }
}
