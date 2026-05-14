// Singleton in-memory cache of platform icon SVGs as blob URLs.
//
// Why: `/assets/platforms/*.svg` is served without explicit cache
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

const cache = reactive(new Map<string, string>());
const inflight = new Set<string>();

export function getCachedPlatformIcon(slug: string): string | undefined {
  return cache.get(slug.toLowerCase());
}

async function fetchOne(slug: string): Promise<void> {
  const key = slug.toLowerCase();
  if (cache.has(key) || inflight.has(key)) return;
  inflight.add(key);
  try {
    const res = await fetch(`/assets/platforms/${key}.svg`);
    if (!res.ok) return;
    const blob = await res.blob();
    // SPA fallbacks (200 + HTML) and other non-image bodies must not
    // land in the cache — they'd render as a broken-image icon
    // downstream. Trust blob.type since it's set by the parser, not
    // by the response header alone.
    if (!blob.type || !blob.type.startsWith("image/")) return;
    cache.set(key, URL.createObjectURL(blob));
  } catch {
    // Swallow — `CachedPlatformIcon`'s own .ico / default fallback
    // chain handles legitimate misses on-demand when the cache miss
    // falls through to a real `<img>` load.
  } finally {
    inflight.delete(key);
  }
}

/**
 * Drop a slug's cached entry. Called by CachedPlatformIcon when its
 * `<img>` reports a render error, so the next render falls through
 * to its own fallback chain (.ico → default.ico) instead of leaving
 * the broken-image glyph on screen.
 */
export function invalidatePlatformIcon(slug: string): void {
  const key = slug.toLowerCase();
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
