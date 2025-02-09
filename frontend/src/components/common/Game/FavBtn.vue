<script setup lang="ts">
import collectionApi, {
  type UpdatedCollection,
} from "@/services/api/collection";
import storeCollections, { type Collection } from "@/stores/collections";
import storeRoms from "@/stores/roms";
import { type SimpleRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";

// Props
const props = defineProps<{ rom: SimpleRom }>();
const romsStore = storeRoms();
const collectionsStore = storeCollections();
const { favCollection } = storeToRefs(collectionsStore);
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");

// Functions
async function switchFromFavourites() {
  if (!favCollection.value) {
    await collectionApi
      .createCollection({
        collection: { name: "Favourites" } as UpdatedCollection,
      })
      .then(({ data }) => {
        collectionsStore.add(data);
        favCollection.value = data;
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
        return;
      });
  }
  if (!collectionsStore.isFav(props.rom)) {
    favCollection.value?.rom_ids.push(props.rom.id);
  } else {
    if (favCollection.value) {
      favCollection.value.rom_ids = favCollection.value.rom_ids.filter(
        (id) => id !== props.rom.id,
      );
      if (romsStore.currentCollection?.name.toLowerCase() == "favourites") {
        romsStore.remove([props.rom]);
      }
    }
  }
  await collectionApi
    .updateCollection({ collection: favCollection.value as Collection })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: `${props.rom.name} ${
          collectionsStore.isFav(props.rom) ? "added to" : "removed from"
        } ${favCollection.value?.name} successfully!`,
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
</script>

<template>
  <v-btn
    v-if="auth.scopes.includes('roms.user.write')"
    @click.stop="switchFromFavourites"
    class="translucent text-shadow"
    rouded="0"
    size="small"
    variant="text"
    ><v-icon color="primary">{{
      collectionsStore.isFav(rom) ? "mdi-star" : "mdi-star-outline"
    }}</v-icon></v-btn
  >
</template>
