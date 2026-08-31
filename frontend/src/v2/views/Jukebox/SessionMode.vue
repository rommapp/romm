<script setup lang="ts">
// The "one big queue" jukebox screens: play-all, free radio, favorites and
// recently added differ only in which query fills the queue.
import { computed, watch } from "vue";
import musicApi from "@/services/api/music";
import useMusicFavorites from "@/stores/musicFavorites";
import SoundtrackPanel from "@/v2/components/Soundtrack/Panel.vue";
import {
  useTrackPager,
  type TrackPageFetcher,
} from "@/v2/composables/useTrackPager";
import { buildFreeRadioSession } from "@/v2/utils/freeRadio";
import {
  RECENTLY_ADDED_LIMIT,
  type JukeboxPlayerMode,
} from "@/v2/utils/jukebox";
import { panelTracksFromCatalog } from "@/v2/utils/soundtrackTracks";

// Enough to fill the hour-long station even when tracks are short and many
// lack the duration metadata the session builder needs.
const STATION_SAMPLE_SIZE = 200;

const props = defineProps<{
  mode: Extract<
    JukeboxPlayerMode,
    "play-all" | "station" | "favorite" | "recent"
  >;
  /** Bumped by the host to force a refetch (e.g. after a delete). */
  refreshToken?: number;
  deletable?: boolean;
}>();
const emit = defineEmits<{
  (e: "delete-track", fileId: number, romId: number): void;
}>();

const favorites = useMusicFavorites();

const pager = useTrackPager((items) => favorites.merge(items));

/** A page of a filtered track query. */
function pagedFetcher(
  load: typeof musicApi.getTracks,
  filters: Parameters<typeof musicApi.getTracks>[0] = {},
): TrackPageFetcher {
  return async (offset, limit) => {
    const { data } = await load({ ...filters, offset, limit });
    return { items: data.items, total: data.total };
  };
}

/** The station and "recently added" are fixed-size sets, so they resolve to a
 *  single page rather than a window onto a larger query. */
function fixedFetcher(load: () => Promise<{ items: unknown[] }>) {
  return (async (offset) => {
    if (offset > 0) return { items: [], total: 0 };
    const { items } = await load();
    return { items, total: items.length };
  }) as TrackPageFetcher;
}

function fetcherFor(mode: typeof props.mode): TrackPageFetcher {
  if (mode === "favorite") return pagedFetcher(musicApi.getFavorites);
  if (mode === "recent") {
    return fixedFetcher(async () => {
      const { data } = await musicApi.getTracks({
        orderBy: "added",
        orderDir: "desc",
        limit: RECENTLY_ADDED_LIMIT,
      });
      return { items: data.items };
    });
  }
  if (mode === "station") {
    return fixedFetcher(async () => ({
      items: buildFreeRadioSession(
        await musicApi.getSampleTracks(STATION_SAMPLE_SIZE),
      ),
    }));
  }
  return pagedFetcher(musicApi.getTracks);
}

watch(
  [() => props.mode, () => props.refreshToken],
  () => void pager.reset(fetcherFor(props.mode)),
  { immediate: true },
);

const panelTracks = computed(() => panelTracksFromCatalog(pager.tracks.value));
</script>

<template>
  <SoundtrackPanel
    :key="mode"
    :tracks="panelTracks"
    :loading="pager.loading.value"
    :loading-more="pager.loadingMore.value"
    :total-tracks="pager.total.value"
    :start-shuffled="mode === 'station'"
    :deletable="deletable"
    wide
    class="jukebox__session"
    @reached="pager.loadMoreIfNear"
    @delete-track="(fileId, romId) => emit('delete-track', fileId, romId)"
  />
</template>

<style scoped>
.jukebox__session {
  grid-column: 1 / -1;
  min-width: 0;
  min-height: 0;
}
</style>
