// Cover-source resolver for collection mosaic surfaces (tile, list row,
// info panel header, picker row). Regular collections expose a custom
// uploaded cover via `path_cover_small` — when set, it wins over the
// ROM-derived mosaic so the user's chosen artwork actually surfaces.
// Virtual/smart collections always have a null `path_cover_small` so
// they fall through to the multi-cover mosaic.
export function collectionCoverList(
  collection: {
    path_cover_small?: string | null;
    path_covers_small?: string[];
  },
  toWebp: (url: string) => string,
): string[] {
  if (collection.path_cover_small) {
    return [toWebp(collection.path_cover_small)];
  }
  return (collection.path_covers_small ?? []).slice(0, 4).map(toWebp);
}
