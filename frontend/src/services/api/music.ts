import type {
  MusicPage_MusicTrackSchema_,
  MusicTrackIdsPayload,
  MusicTrackSchema,
} from "@/__generated__";
import api from "@/services/api";

export const ALL_TRACKS_PAGE_SIZE = 1_000;

export interface MusicTrackFilters {
  search?: string;
  limit?: number;
  offset?: number;
  romId?: number;
}

async function getTracks(filters: MusicTrackFilters = {}) {
  return api.get<MusicPage_MusicTrackSchema_>("/music/tracks", {
    params: {
      search: filters.search || undefined,
      limit: filters.limit ?? ALL_TRACKS_PAGE_SIZE,
      offset: filters.offset ?? 0,
      rom_id: filters.romId,
    },
  });
}

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

async function addFavorites(payload: MusicTrackIdsPayload) {
  return api.post<{ added: number }>("/music/favorites", payload);
}

async function removeFavorites(payload: MusicTrackIdsPayload) {
  return api.delete<{ removed: number }>("/music/favorites", { data: payload });
}

export default { getTracks, getAllTracks, addFavorites, removeFavorites };
