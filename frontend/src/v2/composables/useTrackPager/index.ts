// Incremental loading for a track list: fetch one page, ask for the next
// only when the viewer (or playback) nears the end of what is loaded.
import { computed, ref, shallowRef } from "vue";
import type { MusicTrackSchema } from "@/__generated__";

export const TRACK_PAGE_SIZE = 200;

/** How close to the end of the loaded tracks before the next page is asked
 *  for — enough that scrolling and "next track" rarely hit the boundary. */
const PREFETCH_MARGIN = 50;

export interface TrackPage {
  items: MusicTrackSchema[];
  total: number;
}

export type TrackPageFetcher = (
  offset: number,
  limit: number,
) => Promise<TrackPage>;

export function useTrackPager(onPage?: (items: MusicTrackSchema[]) => void) {
  const tracks = shallowRef<MusicTrackSchema[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const loadingMore = ref(false);

  let fetcher: TrackPageFetcher | null = null;
  // Bumped on every reset so a slow page from a previous selection can't
  // append itself onto the new one.
  let token = 0;

  const hasMore = computed(() => tracks.value.length < total.value);

  async function fetchPage(offset: number): Promise<void> {
    if (!fetcher) return;
    const current = token;
    const page = await fetcher(offset, TRACK_PAGE_SIZE);
    if (current !== token) return;
    tracks.value = offset === 0 ? page.items : [...tracks.value, ...page.items];
    total.value = page.total;
    onPage?.(page.items);
  }

  /** Swaps in a new source and loads its first page. */
  async function reset(next: TrackPageFetcher | null): Promise<void> {
    token += 1;
    fetcher = next;
    tracks.value = [];
    total.value = 0;
    if (!next) return;
    loading.value = true;
    try {
      await fetchPage(0);
    } catch {
      // Leaves the list empty; the host renders its own empty state.
    } finally {
      loading.value = false;
    }
  }

  async function loadMore(): Promise<void> {
    if (loadingMore.value || loading.value || !hasMore.value) return;
    loadingMore.value = true;
    try {
      await fetchPage(tracks.value.length);
    } catch {
      // A failed page just means `hasMore` stays true and it can retry.
    } finally {
      loadingMore.value = false;
    }
  }

  /** Called with the last index the consumer has reached. */
  function loadMoreIfNear(index: number): void {
    if (index >= tracks.value.length - PREFETCH_MARGIN) void loadMore();
  }

  return {
    tracks,
    total,
    loading,
    loadingMore,
    hasMore,
    reset,
    loadMore,
    loadMoreIfNear,
  };
}
