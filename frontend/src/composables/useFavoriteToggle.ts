import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import collectionApi from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

export function useFavoriteToggle(emitter?: Emitter<Events>) {
  const collectionsStore = storeCollections();
  const romsStore = storeRoms();
  const { favoriteCollection } = storeToRefs(collectionsStore);

  async function ensureFavoriteCollection() {
    if (favoriteCollection.value) return favoriteCollection.value;
    // Attempt to refetch collections if not already present
    if (!collectionsStore.allCollections.length) {
      await collectionsStore.fetchCollections();
    }
    if (favoriteCollection.value) return favoriteCollection.value;
    // Create if still missing
    const data = await collectionApi.createCollection({
      collection: {
        name: "Favorites",
        rom_ids: [],
        is_favorite: true,
        is_public: false,
      },
    });
    collectionsStore.addCollection(data);
    collectionsStore.setFavoriteCollection(data);
    emitter?.emit("snackbarShow", {
      msg: `Collection ${data.name} created successfully!`,
      icon: "mdi-check-bold",
      color: "green",
      timeout: 2000,
    });
    return data;
  }

  function isFavorite(rom: SimpleRom) {
    return collectionsStore.isFavorite(rom);
  }

  async function toggleFavorite(rom: SimpleRom) {
    const fav = await ensureFavoriteCollection();
    const currentlyFav = fav.rom_ids?.includes(rom.id) ?? false;

    try {
      const { data } = currentlyFav
        ? await collectionApi.removeRomsFromCollection(fav.id, [rom.id])
        : await collectionApi.addRomsToCollection(fav.id, [rom.id]);

      collectionsStore.updateCollection(data);
      collectionsStore.setFavoriteCollection(data);

      if (currentlyFav && romsStore.currentCollection?.id === fav.id) {
        romsStore.remove([rom]);
      }

      emitter?.emit("snackbarShow", {
        msg: `${rom.name} ${currentlyFav ? "removed from" : "added to"} ${data.name} successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    } catch (error: unknown) {
      const detail = (error as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      emitter?.emit("snackbarShow", {
        msg: detail || "Failed to update favorites",
        icon: "mdi-close-circle",
        color: "red",
      });
      throw error;
    } finally {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    }
  }

  return {
    favoriteCollection,
    ensureFavoriteCollection,
    toggleFavorite,
    isFavorite,
  };
}

export default useFavoriteToggle;
