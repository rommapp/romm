// RomM's Workbox service worker precaches index.html (and a few root files) by MD5
// revision. When the module changes one of those files, its revision must change too,
// or browsers that installed the stock worker keep serving the stock copy.
import { createHash } from "node:crypto";

export function md5(buf) {
  return createHash("md5").update(buf).digest("hex");
}

/**
 * changed: { "index.html": Buffer|string, ... } keyed by precache url.
 * Returns { text, updated: [url...] }.
 */
export function updatePrecacheRevisions(swText, changed) {
  const updated = [];
  let text = swText;
  for (const [url, content] of Object.entries(changed)) {
    const escaped = url.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`(\\{\\s*"?url"?\\s*:\\s*"${escaped}"\\s*,\\s*"?revision"?\\s*:\\s*")([0-9a-f]+)(")`, "g");
    let hit = false;
    text = text.replace(re, (_, a, _old, b) => {
      hit = true;
      return a + md5(content) + b;
    });
    if (hit) updated.push(url);
  }
  return { text, updated };
}
