import { defineStore } from "pinia";
import { computed, ref } from "vue";
import musicApi from "@/services/api/music";
import { playerTrackKey } from "@/stores/soundtrackPlayer";

/** A favorited track: its file, and the song within it for multi-song files. */
interface FavoriteTrack {
  rom_file_id: number;
  song?: number;
  is_favorite?: boolean;
}

function keyOf(fileId: number, song = 0): string {
  return playerTrackKey({ fileId, song });
}

const useMusicFavorites = defineStore("musicFavorites", () => {
  const favoriteIds = ref<Set<string>>(new Set());
  const pendingIds = ref<Set<string>>(new Set());

  const count = computed(() => favoriteIds.value.size);

  function isFavorite(fileId: number, song = 0): boolean {
    return favoriteIds.value.has(keyOf(fileId, song));
  }

  function isPending(fileId: number, song = 0): boolean {
    return pendingIds.value.has(keyOf(fileId, song));
  }

  /** Seed from any payload that carries `is_favorite`, without dropping
   *  knowledge of tracks outside it. */
  function merge(tracks: FavoriteTrack[]) {
    for (const track of tracks) {
      const key = keyOf(track.rom_file_id, track.song);
      if (track.is_favorite) favoriteIds.value.add(key);
      else favoriteIds.value.delete(key);
    }
  }

  /** Flips one track and returns the new state, or null if the call failed. */
  async function toggle(fileId: number, song = 0): Promise<boolean | null> {
    const key = keyOf(fileId, song);
    if (pendingIds.value.has(key)) return null;
    const next = !favoriteIds.value.has(key);
    pendingIds.value.add(key);
    try {
      const payload = { tracks: [{ rom_file_id: fileId, song }] };
      if (next) await musicApi.addFavorites(payload);
      else await musicApi.removeFavorites(payload);
      if (next) favoriteIds.value.add(key);
      else favoriteIds.value.delete(key);
      return next;
    } catch {
      return null;
    } finally {
      pendingIds.value.delete(key);
    }
  }

  function reset() {
    favoriteIds.value = new Set();
    pendingIds.value = new Set();
  }

  return {
    favoriteIds,
    count,
    isFavorite,
    isPending,
    merge,
    toggle,
    reset,
  };
});

export default useMusicFavorites;
