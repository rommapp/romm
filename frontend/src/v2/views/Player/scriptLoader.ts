// Shared runtime injection for the player views. EmulatorJS and js-dos serve
// their runtime locally in the full image and fall back to a CDN without it.

/** Inject a <script> and resolve once it has executed. */
export function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Failed loading ${src}`));
    document.body.appendChild(s);
  });
}

/**
 * Check that a URL really serves JavaScript.
 *
 * The Vite dev server and many SPA hosts answer a missing asset with 200 plus
 * index.html, which a <script> tag loads without ever firing onerror.
 *
 * @param url The script URL to pre-flight.
 * @returns True when the body is JavaScript, false otherwise.
 */
export async function isJsResource(url: string): Promise<boolean> {
  try {
    const res = await fetch(url);
    if (!res.ok) return false;
    const ct = res.headers.get("content-type") ?? "";
    if (/javascript|ecmascript/i.test(ct)) return true;
    if (/text\/html/i.test(ct)) return false;
    // Content-Type may be absent (older servers); sniff the body.
    const text = await res.clone().text();
    return !text.trimStart().startsWith("<");
  } catch {
    return false;
  }
}
