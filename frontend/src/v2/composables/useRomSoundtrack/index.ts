// Loads one ROM's soundtrack files into the panel's normalized track shape.
import axios from "axios";
import { computed, ref, toValue, watch, type MaybeRefOrGetter } from "vue";
import type {
  SoundtrackTrackMetaSchema,
  TrackMetaSchema,
} from "@/__generated__";
import musicApi from "@/services/api/music";
import romApi from "@/services/api/rom";
import useMusicFavorites from "@/stores/musicFavorites";
import type { DetailedRom } from "@/stores/roms";
import { resolveSoundtrackGameArtwork } from "@/stores/soundtrackPlayer";
import {
  panelTracksFromRom,
  romFolderCoverUrl,
  type PanelTrack,
} from "@/v2/utils/soundtrackTracks";

export function useRomSoundtrack(rom: MaybeRefOrGetter<DetailedRom | null>) {
  const favorites = useMusicFavorites();
  const metaByFileId = ref<Map<number, TrackMetaSchema>>(new Map());
  const loading = ref(false);
  const failed = ref(false);
  let abort: AbortController | null = null;

  const current = computed(() => toValue(rom));

  const gameArtworkUrl = computed(() => {
    const value = current.value;
    return value ? resolveSoundtrackGameArtwork(value) : undefined;
  });

  const fallbackArtUrl = computed(() => {
    const value = current.value;
    if (!value) return undefined;
    return romFolderCoverUrl(value) ?? gameArtworkUrl.value;
  });

  const tracks = computed<PanelTrack[]>(() => {
    const value = current.value;
    if (!value) return [];
    return panelTracksFromRom(value, metaByFileId.value, gameArtworkUrl.value);
  });

  async function load() {
    const value = current.value;
    if (!value) {
      metaByFileId.value = new Map();
      return;
    }
    abort?.abort();
    abort = new AbortController();
    const signal = abort.signal;
    loading.value = true;
    failed.value = false;
    try {
      // Independent requests: favorite state never gates playback, so the two
      // fly together and a failed catalog fetch leaves the metadata intact.
      const [meta, catalog] = await Promise.all([
        romApi.getSoundtrackMetadata({ romId: value.id, signal }),
        musicApi.getAllTracks({ romId: value.id }).catch(() => null),
      ]);
      if (signal.aborted) return;
      const next = new Map<number, TrackMetaSchema>();
      for (const row of meta.data as SoundtrackTrackMetaSchema[]) {
        if (row.track_meta) next.set(row.file_id, row.track_meta);
      }
      metaByFileId.value = next;
      if (catalog) favorites.merge(catalog);
    } catch (err) {
      if (axios.isCancel(err) || signal.aborted) return;
      failed.value = true;
    } finally {
      if (!signal.aborted) loading.value = false;
    }
  }

  watch(
    () => [current.value?.id, current.value?.updated_at] as const,
    () => void load(),
    { immediate: true },
  );

  function dispose() {
    abort?.abort();
  }

  return { tracks, loading, failed, fallbackArtUrl, reload: load, dispose };
}
