import type {
  MusicPage_MusicTrackSchema_,
  MusicTrackIdsPayload,
  MusicTrackSchema,
} from "@/__generated__";
import api from "@/services/api";

export interface MusicTrackFilters {
  search?: string;
  limit?: number;
  offset?: number;
  romId?: number;
  orderBy?:
    | "title"
    | "artist"
    | "album"
    | "duration"
    | "year"
    | "platform"
    | "added";
  orderDir?: "asc" | "desc";
}

async function getTracks(filters: MusicTrackFilters = {}) {
  return api.get<MusicPage_MusicTrackSchema_>("/music/tracks", {
    params: {
      search: filters.search || undefined,
      limit: filters.limit ?? 10_000,
      offset: filters.offset ?? 0,
      rom_id: filters.romId,
      order_by: filters.orderBy ?? "title",
      order_dir: filters.orderDir ?? "asc",
    },
  });
}

const ALL_TRACKS_PAGE_SIZE = 1_000;

async function getAllTracks(
  filters: Omit<MusicTrackFilters, "limit" | "offset"> = {},
): Promise<MusicTrackSchema[]> {
  const tracks: MusicTrackSchema[] = [];
  let total = Number.POSITIVE_INFINITY;

  while (tracks.length < total) {
    const { data } = await getTracks({
      ...filters,
      limit: ALL_TRACKS_PAGE_SIZE,
      offset: tracks.length,
    });
    tracks.push(...data.items);
    total = data.total;
    if (data.items.length === 0) break;
  }

  return tracks;
}

async function addFavorites(payload: MusicTrackIdsPayload) {
  return api.post<{ added: number }>("/music/favorites", payload);
}

async function removeFavorites(payload: MusicTrackIdsPayload) {
  return api.delete<{ removed: number }>("/music/favorites", { data: payload });
}

export default { getTracks, getAllTracks, addFavorites, removeFavorites };
