import { contextBridge, ipcRenderer } from "electron";

// The setup page is local and only ever needs to hand back one string.
contextBridge.exposeInMainWorld("rommSetup", {
  save: (serverUrl: string): Promise<void> =>
    ipcRenderer.invoke("setup:save", serverUrl),
});
