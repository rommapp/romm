// The js-dos runtime is a document-level singleton: one injection and one asset
// base however many launch views mount. Held as the in-flight promise, so a
// view mounting while another is still loading waits for that load instead of
// injecting a second copy of a runtime that declares its own globals.
import { isJsResource, loadScript } from "@/v2/utils/scriptLoader";

export const LOCAL_BASE = "/assets/jsdos";
// Fallback for slim images and the dev server, which ship no local copy. Pinned
// to the image's JSDOS_VERSION; jsDelivr sends the CORP a directly opened player
// document needs under its COEP.
export const CDN_BASE = "https://cdn.jsdelivr.net/npm/js-dos@8.4.1/dist";

let pending: Promise<string> | null = null;
// A retry after a failed script load would otherwise stack a second stylesheet.
let styledBase: string | null = null;

/** Load the runtime, resolving with the base the emulator payloads follow. */
export function loadJsDosRuntime(): Promise<string> {
  pending ??= inject().catch((error: unknown) => {
    // A failed load is not the document's verdict, so let the next mount retry.
    pending = null;
    throw error;
  });
  return pending;
}

async function inject(): Promise<string> {
  const base = (await isJsResource(`${LOCAL_BASE}/js-dos.js`))
    ? LOCAL_BASE
    : CDN_BASE;

  if (styledBase !== base) {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = `${base}/js-dos.css`;
    document.head.appendChild(css);
    styledBase = base;
  }

  await loadScript(`${base}/js-dos.js`);
  return base;
}
