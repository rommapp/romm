import { contextBridge, ipcRenderer } from "electron";
import type {
  LaunchRequest,
  LaunchResult,
  LaunchState,
  PlatformSupport,
  PlatformSupportQuery,
  RommNativeBridge,
} from "../shared/types.ts";

const VERSION_FLAG = "--romm-shell-version=";

function shellVersion(): string {
  const flag = process.argv.find((arg) => arg.startsWith(VERSION_FLAG));
  return flag ? flag.slice(VERSION_FLAG.length) : "0.0.0";
}

const LAUNCH_STATE_CHANNEL = "romm:launch-state";

const bridge: RommNativeBridge = {
  shellVersion: shellVersion(),
  os: process.platform as RommNativeBridge["os"],

  launch: (request: LaunchRequest): Promise<LaunchResult> =>
    ipcRenderer.invoke("romm:launch", request),

  cancel: (romId: number): Promise<void> =>
    ipcRenderer.invoke("romm:cancel", romId),

  getPlatformSupport: (query: PlatformSupportQuery): Promise<PlatformSupport> =>
    ipcRenderer.invoke("romm:platform-support", query),

  onLaunchState: (listener: (state: LaunchState) => void): (() => void) => {
    // The Electron event object never reaches the renderer: only the payload
    // crosses the bridge, so the page cannot reach back through event.sender.
    const handler = (_event: unknown, state: LaunchState) => listener(state);
    ipcRenderer.on(LAUNCH_STATE_CHANNEL, handler);
    return () => ipcRenderer.off(LAUNCH_STATE_CHANNEL, handler);
  },

  openSettings: (): Promise<void> => ipcRenderer.invoke("romm:open-settings"),
};

contextBridge.exposeInMainWorld("rommNative", bridge);
