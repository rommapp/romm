const REMOTE_URL = /^https?:\/\//i;

/** Route a metadata provider's image through RomM's own origin, so pages served
 *  with `Cross-Origin-Embedder-Policy: require-corp` can still embed it. */
export function providerImageUrl(url: string): string {
  if (!REMOTE_URL.test(url)) return url;
  return `/api/search/image?url=${encodeURIComponent(url)}`;
}
