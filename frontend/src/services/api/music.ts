import type {
  FacetValueSchema,
  MusicGameFacetSchema,
  MusicPage_FacetValueSchema_,
  MusicPage_MusicGameFacetSchema_,
  MusicPage_MusicPlatformFacetSchema_,
  MusicPage_MusicTrackSchema_,
  MusicPlatformFacetSchema,
  MusicStatsSchema,
  MusicTrackIdsPayload,
  MusicTrackSchema,
} from "@/__generated__";
import api from "@/services/api";

export const ALL_TRACKS_PAGE_SIZE = 1_000;

/** Server-side track filters. Every browse mode maps onto these, so no mode
 *  has to fetch the whole catalog and re-group it in the client. */
export interface MusicTrackFilters {
  search?: string;
  artist?: string;
  gameGenre?: string;
  platformIds?: number[];
  romId?: number;
  minYear?: number;
  maxYear?: number;
  orderBy?:
    "title" | "artist" | "album" | "duration" | "year" | "platform" | "added";
  orderDir?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

function trackParams(filters: MusicTrackFilters) {
  return {
    search: filters.search || undefined,
    artist: filters.artist || undefined,
    game_genre: filters.gameGenre || undefined,
    platform_ids: filters.platformIds?.length ? filters.platformIds : undefined,
    rom_id: filters.romId,
    min_year: filters.minYear,
    max_year: filters.maxYear,
    order_by: filters.orderBy,
    order_dir: filters.orderDir,
    limit: filters.limit ?? ALL_TRACKS_PAGE_SIZE,
    offset: filters.offset ?? 0,
  };
}

async function getTracks(filters: MusicTrackFilters = {}) {
  return api.get<MusicPage_MusicTrackSchema_>("/music/tracks", {
    params: trackParams(filters),
  });
}

async function getFavorites(filters: MusicTrackFilters = {}) {
  return api.get<MusicPage_MusicTrackSchema_>("/music/favorites", {
    params: trackParams(filters),
  });
}

/** Pages a small-by-construction list (one game's soundtrack) to completion;
 *  anything unbounded pages on demand through `useTrackPager` instead. */
async function getAllTracks(
  filters: Omit<MusicTrackFilters, "limit" | "offset"> = {},
): Promise<MusicTrackSchema[]> {
  const { data: first } = await getTracks({
    ...filters,
    limit: ALL_TRACKS_PAGE_SIZE,
    offset: 0,
  });
  if (first.items.length === 0) return [];

  // The first page reports the total, so the rest are independent.
  const offsets: number[] = [];
  for (
    let offset = ALL_TRACKS_PAGE_SIZE;
    offset < first.total;
    offset += ALL_TRACKS_PAGE_SIZE
  ) {
    offsets.push(offset);
  }
  const rest = await Promise.all(
    offsets.map((offset) =>
      getTracks({ ...filters, limit: ALL_TRACKS_PAGE_SIZE, offset }),
    ),
  );

  return [...first.items, ...rest.flatMap(({ data }) => data.items)];
}

export interface FacetFilters {
  search?: string;
  limit?: number;
  offset?: number;
}

const FACET_PAGE_SIZE = 500;

function facetParams(filters: FacetFilters) {
  return {
    search: filters.search || undefined,
    limit: filters.limit ?? FACET_PAGE_SIZE,
    offset: filters.offset ?? 0,
    order_by: "value",
    order_dir: "asc",
  };
}

async function getArtists(filters: FacetFilters = {}) {
  return api.get<MusicPage_FacetValueSchema_>("/music/artists", {
    params: facetParams(filters),
  });
}

async function getGameGenres(filters: FacetFilters = {}) {
  return api.get<MusicPage_FacetValueSchema_>("/music/game-genres", {
    params: facetParams(filters),
  });
}

async function getYears(filters: FacetFilters = {}) {
  return api.get<MusicPage_FacetValueSchema_>("/music/years", {
    params: facetParams(filters),
  });
}

async function getPlatforms(filters: FacetFilters = {}) {
  return api.get<MusicPage_MusicPlatformFacetSchema_>("/music/platforms", {
    params: facetParams(filters),
  });
}

async function getGames(filters: FacetFilters = {}) {
  return api.get<MusicPage_MusicGameFacetSchema_>("/music/games", {
    params: facetParams(filters),
  });
}

/** A bounded sample of the catalog, pulled from random offsets. */
async function getSampleTracks(
  maxTracks: number,
  filters: Omit<MusicTrackFilters, "limit" | "offset"> = {},
): Promise<MusicTrackSchema[]> {
  const pageSize = Math.min(maxTracks, ALL_TRACKS_PAGE_SIZE);
  const { data: first } = await getTracks({
    ...filters,
    limit: pageSize,
    offset: 0,
  });
  if (first.total <= pageSize) return first.items;

  const pages = Math.ceil(maxTracks / pageSize);
  const maxOffset = Math.max(0, first.total - pageSize);
  const offsets = new Set<number>();
  for (let i = 0; i < pages; i += 1) {
    offsets.add(Math.floor(Math.random() * (maxOffset + 1)));
  }
  const sampled = await Promise.all(
    [...offsets].map((offset) =>
      getTracks({ ...filters, limit: pageSize, offset }),
    ),
  );
  return sampled.flatMap(({ data }) => data.items).slice(0, maxTracks);
}

async function getStats() {
  return api.get<MusicStatsSchema>("/music/stats");
}

async function addFavorites(payload: MusicTrackIdsPayload) {
  return api.post<{ added: number }>("/music/favorites", payload);
}

async function removeFavorites(payload: MusicTrackIdsPayload) {
  return api.delete<{ removed: number }>("/music/favorites", { data: payload });
}

export type {
  FacetValueSchema,
  MusicGameFacetSchema,
  MusicPlatformFacetSchema,
};

export default {
  getTracks,
  getAllTracks,
  getSampleTracks,
  getFavorites,
  getArtists,
  getGameGenres,
  getYears,
  getPlatforms,
  getGames,
  getStats,
  addFavorites,
  removeFavorites,
};
