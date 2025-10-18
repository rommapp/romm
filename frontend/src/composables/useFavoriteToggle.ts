import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import collectionApi from "@/services/api/collection";
import storeCollections, { type Collection } from "@/stores/collections";
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
    const { data } = await collectionApi.createCollection({
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
    if (!fav.rom_ids) (fav as Collection).rom_ids = [] as unknown as number[]; // ensure array exists

    const currentlyFav = fav.rom_ids.includes(rom.id);
    if (currentlyFav) {
      fav.rom_ids = fav.rom_ids.filter((id) => id !== rom.id);
      if (romsStore.currentCollection?.id === fav.id) {
        romsStore.remove([rom]);
      }
    } else {
      fav.rom_ids.push(rom.id);
    }

    try {
      const { data } = await collectionApi.updateCollection({
        collection: fav as Collection,
      });
      collectionsStore.updateCollection(data);
      collectionsStore.setFavoriteCollection(data);
      emitter?.emit("snackbarShow", {
        msg: `${rom.name} ${currentlyFav ? "removed from" : "added to"} ${data.name} successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    } catch (error: unknown) {
      // Rollback
      if (currentlyFav) {
        fav.rom_ids.push(rom.id);
      } else {
        fav.rom_ids = fav.rom_ids.filter((id) => id !== rom.id);
      }
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
