import { defineStore } from "pinia";
import { computed, ref } from "vue";
import musicApi from "@/services/api/music";

const useMusicFavorites = defineStore("musicFavorites", () => {
  const favoriteIds = ref<Set<number>>(new Set());
  const pendingIds = ref<Set<number>>(new Set());

  const count = computed(() => favoriteIds.value.size);

  function isFavorite(fileId: number): boolean {
    return favoriteIds.value.has(fileId);
  }

  function isPending(fileId: number): boolean {
    return pendingIds.value.has(fileId);
  }

  /** Seed from any payload that carries `is_favorite`, without dropping
   *  knowledge of tracks outside it. */
  function merge(tracks: { rom_file_id: number; is_favorite?: boolean }[]) {
    for (const track of tracks) {
      if (track.is_favorite) favoriteIds.value.add(track.rom_file_id);
      else favoriteIds.value.delete(track.rom_file_id);
    }
  }

  /** Flips one track and returns the new state, or null if the call failed. */
  async function toggle(fileId: number): Promise<boolean | null> {
    if (pendingIds.value.has(fileId)) return null;
    const next = !favoriteIds.value.has(fileId);
    pendingIds.value.add(fileId);
    try {
      const payload = { rom_file_ids: [fileId] };
      if (next) await musicApi.addFavorites(payload);
      else await musicApi.removeFavorites(payload);
      if (next) favoriteIds.value.add(fileId);
      else favoriteIds.value.delete(fileId);
      return next;
    } catch {
      return null;
    } finally {
      pendingIds.value.delete(fileId);
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
