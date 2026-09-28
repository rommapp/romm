import { defineStore } from "pinia";
import { computed, ref } from "vue";
import musicApi from "@/services/api/music";

const useMusicFavorites = defineStore("musicFavorites", () => {
  const favoriteIds = ref<Set<number>>(new Set());
  const pendingIds = ref<Set<number>>(new Set());

  const count = computed(() => favoriteIds.value.size);

  function isFavorite(trackId: number): boolean {
    return favoriteIds.value.has(trackId);
  }

  function isPending(trackId: number): boolean {
    return pendingIds.value.has(trackId);
  }

  /** Seed from any payload that carries `is_favorite`, without dropping
   *  knowledge of tracks outside it. */
  function merge(tracks: { id: number; is_favorite?: boolean }[]) {
    for (const track of tracks) {
      if (track.is_favorite) favoriteIds.value.add(track.id);
      else favoriteIds.value.delete(track.id);
    }
  }

  /** Flips one track and returns the new state, or null if the call failed. */
  async function toggle(trackId: number): Promise<boolean | null> {
    if (pendingIds.value.has(trackId)) return null;
    const next = !favoriteIds.value.has(trackId);
    pendingIds.value.add(trackId);
    try {
      const payload = { track_ids: [trackId] };
      if (next) await musicApi.addFavorites(payload);
      else await musicApi.removeFavorites(payload);
      if (next) favoriteIds.value.add(trackId);
      else favoriteIds.value.delete(trackId);
      return next;
    } catch {
      return null;
    } finally {
      pendingIds.value.delete(trackId);
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
