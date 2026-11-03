// RomM's service worker precaches root files by MD5 revision; a file the module changes needs
// a new revision, or installed workers keep serving the stock copy.
import { createHash } from "node:crypto";

export function md5(buf) {
  return createHash("md5").update(buf).digest("hex");
}

/** Sets the revision of each changed file ({ url: contents }); returns { text, updated }. */
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
