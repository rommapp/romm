import { BrowserWindow, app } from "electron";
import { loadConfig } from "./config.ts";
import { broadcastLaunchState, registerIpc } from "./ipc.ts";
import { Launcher } from "./launcher.ts";
import {
  createMainWindow,
  createSetupWindow,
  installCertificateTrust,
} from "./window.ts";

const launcher = new Launcher(broadcastLaunchState);

// One instance owns the ROM cache and the launch registry; a second would race
// both, so hand the argv to the window that is already running instead.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const [window] = BrowserWindow.getAllWindows();
    if (!window) return;
    if (window.isMinimized()) window.restore();
    window.focus();
  });

  void start();
}

async function openInitialWindow(): Promise<void> {
  const config = await loadConfig();
  if (config.serverUrl) {
    createMainWindow(config.serverUrl);
    return;
  }
  createSetupWindow((serverUrl) => createMainWindow(serverUrl));
}

async function start(): Promise<void> {
  await app.whenReady();
  installCertificateTrust();
  registerIpc(launcher);
  await openInitialWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void openInitialWindow();
  });
}

app.on("window-all-closed", () => {
  launcher.dispose();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => launcher.dispose());
