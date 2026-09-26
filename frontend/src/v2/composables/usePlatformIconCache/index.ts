// Singleton in-memory cache of platform icons as blob URLs.
//
// Why: `/assets/platforms/*` is served without explicit cache
// headers, so the browser revalidates / re-downloads on every
// `<img>` mount. In tables and menus that render many platform icons,
// this turns into a flood of network requests every time the surface
// opens. Caching the raw blob and reusing a `URL.createObjectURL()`
// URL means subsequent reads are memory-local — zero network for the
// lifetime of the page.
//
// The cache is a `reactive(Map)` so components reading via
// `getCachedPlatformIcon(slug)` automatically re-render when
// `prefetchPlatformIcons()` finishes populating an entry.
//
// SSR / non-browser environments: `window` is guarded; `fetch` and
// `URL.createObjectURL` are no-ops there.
import { reactive } from "vue";
import {
  platformSlugKey,
  shippedPlatformIconUrl,
} from "@/v2/utils/platformIcons";

const cache = reactive(new Map<string, string>());
const inflight = new Set<string>();

export function getCachedPlatformIcon(slug: string): string | undefined {
  return cache.get(platformSlugKey(slug));
}

/** Blob URL for `url`, or null when it is missing or unreadable. */
async function fetchBlobUrl(url: string): Promise<string | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    // The SPA fallback answers with 200 + HTML, which must not reach the
    // cache. Trust blob.type: the parser sets it, the header does not.
    if (!blob.type || !blob.type.startsWith("image/")) return null;
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

async function fetchOne(slug: string): Promise<void> {
  const key = platformSlugKey(slug);
  const url = shippedPlatformIconUrl(key);
  if (!url || cache.has(key) || inflight.has(key)) return;
  inflight.add(key);
  try {
    const blobUrl = await fetchBlobUrl(url);
    if (blobUrl) cache.set(key, blobUrl);
  } finally {
    inflight.delete(key);
  }
}

/**
 * Drop a slug's cached entry. Called by CachedPlatformIcon when its
 * `<img>` reports a render error, so the next render falls back to the
 * shipped URL instead of leaving the broken-image glyph on screen.
 */
export function invalidatePlatformIcon(slug: string): void {
  const key = platformSlugKey(slug);
  const url = cache.get(key);
  if (url) {
    URL.revokeObjectURL(url);
    cache.delete(key);
  }
}

/**
 * Warm the cache for every passed slug. Runs inside
 * `requestIdleCallback` (falling back to `setTimeout(0)`) so the
 * prefetch never competes with the initial paint of the surface
 * that called it.
 */
export function prefetchPlatformIcons(slugs: readonly string[]): void {
  if (typeof window === "undefined") return;
  const run = () => {
    for (const slug of slugs) if (slug) void fetchOne(slug);
  };
  const ric = (
    window as Window & { requestIdleCallback?: (cb: () => void) => number }
  ).requestIdleCallback;
  if (typeof ric === "function") ric(run);
  else setTimeout(run, 0);
}
