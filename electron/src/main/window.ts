import { BrowserWindow, app, dialog, shell } from "electron";
import { join } from "node:path";
import { type DesktopConfig } from "../shared/types.ts";
import { loadConfig, updateConfig } from "./config.ts";

const SETUP_PAGE = join(__dirname, "../../resources/setup.html");

/** Schemes we are willing to hand to the user's browser or shell. */
const EXTERNAL_SCHEMES = new Set(["https:", "http:", "mailto:"]);

function sameOrigin(url: string, serverUrl: string): boolean {
  try {
    return new URL(url).origin === new URL(serverUrl).origin;
  } catch {
    return false;
  }
}

/** Confine a window to its RomM server. The renderer paints metadata from ten
 *  third-party providers, so only same-origin navigation stays in-window. */
function confineToServer(window: BrowserWindow, serverUrl: string): void {
  const openExternally = (url: string): void => {
    try {
      if (EXTERNAL_SCHEMES.has(new URL(url).protocol))
        void shell.openExternal(url);
    } catch {
      // A malformed URL is simply not opened.
    }
  };

  window.webContents.on("will-navigate", (event, url) => {
    if (sameOrigin(url, serverUrl)) return;
    event.preventDefault();
    openExternally(url);
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    openExternally(url);
    return { action: "deny" };
  });

  // Attaching a webview would bypass the checks above, and RomM never uses one.
  window.webContents.on("will-attach-webview", (event) =>
    event.preventDefault(),
  );

  window.webContents.session.setPermissionRequestHandler(
    (_contents, permission, callback) => {
      // Gamepad and fullscreen are what the player needs; nothing else is
      // granted silently to a page rendering third-party metadata.
      callback(permission === "fullscreen" || permission === "pointerLock");
    },
  );
}

function createWindow(preload: string): BrowserWindow {
  return new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 720,
    minHeight: 480,
    backgroundColor: "#000000",
    autoHideMenuBar: true,
    title: "RomM",
    webPreferences: {
      preload,
      // The preload has no Node access to read package metadata, so the shell
      // version it reports to the page is passed in as an argv flag.
      additionalArguments: [`--romm-shell-version=${app.getVersion()}`],
      // The renderer is remote content. It gets no Node, no shared globals
      // with the preload, and its own OS sandbox.
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webviewTag: false,
      webSecurity: true,
      spellcheck: false,
    },
  });
}

export function createSetupWindow(
  onSaved: (serverUrl: string) => void,
): BrowserWindow {
  const window = createWindow(join(__dirname, "../preload/setup.js"));
  void window.loadFile(SETUP_PAGE);
  window.webContents.ipc.handle("setup:save", async (_event, raw: unknown) => {
    const serverUrl = normalizeServerUrl(raw);
    await updateConfig({ serverUrl });
    onSaved(serverUrl);
    window.close();
  });
  return window;
}

/** Accept what a user would actually type and reject anything that is not a web origin. */
export function normalizeServerUrl(raw: unknown): string {
  if (typeof raw !== "string" || raw.trim().length === 0) {
    throw new Error("Enter the address of your RomM server.");
  }
  const candidate = raw.trim();
  const withScheme = /^https?:\/\//i.test(candidate)
    ? candidate
    : `https://${candidate}`;
  const url = new URL(withScheme);
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error("Only http:// and https:// addresses are supported.");
  }
  return url.origin;
}

export function createMainWindow(serverUrl: string): BrowserWindow {
  const window = createWindow(join(__dirname, "../preload/index.js"));
  confineToServer(window, serverUrl);
  void window.loadURL(serverUrl);
  return window;
}

/** Self-signed certificates are common on a LAN, so ask once and remember the
 *  fingerprint rather than locking those servers out. */
export function installCertificateTrust(): void {
  app.on(
    "certificate-error",
    (event, webContents, url, error, certificate, callback) => {
      void (async () => {
        const config: DesktopConfig = await loadConfig();
        if (config.trustedCertificates.includes(certificate.fingerprint)) {
          event.preventDefault();
          callback(true);
          return;
        }

        const parent = BrowserWindow.fromWebContents(webContents);
        const options = {
          type: "warning" as const,
          buttons: ["Cancel", "Trust this certificate"],
          defaultId: 0,
          cancelId: 0,
          title: "Untrusted certificate",
          message: `The certificate for ${new URL(url).host} could not be verified.`,
          detail: `${error}\n\nFingerprint: ${certificate.fingerprint}\n\nOnly continue if this is your own server.`,
        };
        const { response } = parent
          ? await dialog.showMessageBox(parent, options)
          : await dialog.showMessageBox(options);

        if (response !== 1) {
          callback(false);
          return;
        }

        await updateConfig({
          trustedCertificates: [
            ...config.trustedCertificates,
            certificate.fingerprint,
          ],
        });
        event.preventDefault();
        callback(true);
      })();
    },
  );
}
