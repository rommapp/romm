<script setup lang="ts">
import collectionApi, {
  type UpdatedCollection,
} from "@/services/api/collection";
import storeCollections, { type Collection } from "@/stores/collections";
import { type SimpleRom } from "@/stores/roms.js";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";

// Props
const props = defineProps<{ rom: SimpleRom }>();
const collectionsStore = storeCollections();
const { favCollection } = storeToRefs(collectionsStore);
const emitter = inject<Emitter<Events>>("emitter");

// Functions
function isFav() {
  return favCollection.value?.roms?.includes(props.rom.id);
}

async function switchFromFavourites() {
  if (!favCollection.value) {
    await collectionApi
      .createCollection({
        collection: { name: "Favourites" } as UpdatedCollection,
      })
      .then(({ data }) => {
        collectionsStore.add(data);
        collectionsStore.setFavCollection(data);
        emitter?.emit("snackbarShow", {
          msg: `Collection ${data.name} created successfully!`,
          icon: "mdi-check-bold",
          color: "green",
          timeout: 2000,
        });
      })
      .catch((error) => {
        console.log(error);
        emitter?.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
      });
  } else {
    if (!isFav()) {
      favCollection.value.roms.push(props.rom.id);
    } else {
      favCollection.value.roms = favCollection.value.roms.filter(
        (id) => id !== props.rom.id
      );
    }
    await collectionApi
      .updateCollection({ collection: favCollection.value })
      .then(({ data }) => {
        emitter?.emit("snackbarShow", {
          msg: `Roms added to ${favCollection.value?.name} successfully!`,
          icon: "mdi-check-bold",
          color: "green",
          timeout: 2000,
        });
      })
      .catch((error) => {
        console.log(error);
        emitter?.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
        return;
      })
      .finally(() => {
        emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      });
  }
}
</script>

<template>
  <v-btn
    @click.stop="switchFromFavourites"
    class="translucent text-shadow"
    rouded="0"
    size="x-small"
    variant="text"
    icon
    ><v-icon color="romm-accent-1">{{
      isFav() ? "mdi-star" : "mdi-star-outline"
    }}</v-icon></v-btn
  >
</template>
