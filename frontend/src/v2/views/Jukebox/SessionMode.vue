<script setup lang="ts">
// The "one big queue" jukebox screens: play-all, free radio, favorites and
// recently added. They differ only in which query fills the queue.
import { RSkeletonBlock } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { MusicTrackSchema } from "@/__generated__";
import musicApi from "@/services/api/music";
import useMusicFavorites from "@/stores/musicFavorites";
import SoundtrackPanel from "@/v2/components/Soundtrack/Panel.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import { buildFreeRadioSession } from "@/v2/utils/freeRadio";
import type { JukeboxPlayerMode } from "@/v2/utils/jukebox";
import { panelTracksFromCatalog } from "@/v2/utils/soundtrackTracks";

const RECENTLY_ADDED_LIMIT = 25;

// Comfortably more than an hour of music, without paging a whole library.
const STATION_SAMPLE_SIZE = 1_000;

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

const { t } = useI18n();
const favorites = useMusicFavorites();

const tracks = ref<MusicTrackSchema[]>([]);
const loading = ref(true);
let token = 0;

async function fetchForMode(
  mode: typeof props.mode,
): Promise<MusicTrackSchema[]> {
  if (mode === "favorite") return musicApi.getAllFavorites();
  if (mode === "recent") {
    const { data } = await musicApi.getTracks({
      orderBy: "added",
      orderDir: "desc",
      limit: RECENTLY_ADDED_LIMIT,
    });
    return data.items;
  }
  if (mode === "station") {
    return buildFreeRadioSession(
      await musicApi.getSampleTracks(STATION_SAMPLE_SIZE),
    );
  }
  return musicApi.getAllTracks();
}

async function load(mode: typeof props.mode) {
  const current = ++token;
  loading.value = true;
  try {
    const next = await fetchForMode(mode);
    if (current !== token) return;
    tracks.value = next;
    favorites.merge(next);
  } catch {
    if (current === token) tracks.value = [];
  } finally {
    if (current === token) loading.value = false;
  }
}

watch(() => props.mode, load, { immediate: true });
watch(
  () => props.refreshToken,
  () => void load(props.mode),
);

const panelTracks = computed(() => panelTracksFromCatalog(tracks.value));
</script>

<template>
  <div v-if="loading" class="jukebox__session-loading">
    <RSkeletonBlock height="140px" rounded="md" />
  </div>
  <EmptyState
    v-else-if="!panelTracks.length"
    class="jukebox__session"
    variant="boxed"
    icon="mdi-playlist-music"
    :message="t('common.no-results')"
  />
  <SoundtrackPanel
    v-else
    :key="mode"
    :tracks="panelTracks"
    :start-shuffled="mode === 'station'"
    :deletable="deletable"
    class="jukebox__session"
    @delete-track="(fileId, romId) => emit('delete-track', fileId, romId)"
  />
</template>

<style scoped>
.jukebox__session {
  grid-column: 1 / -1;
  min-width: 0;
  min-height: 0;
}

.jukebox__session-loading {
  grid-column: 1 / -1;
  padding: var(--r-space-5);
}
</style>
