<script setup lang="ts">
import RAvatar from "@/components/common/Collection/RAvatar.vue";
import RDialog from "@/components/common/RDialog.vue";
import collectionApi from "@/services/api/collection";
import storeCollections, { type Collection } from "@/stores/collections";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";

const router = useRouter();
const { lgAndUp } = useDisplay();
const collectionsStore = storeCollections();
const collection = ref<Collection | null>(null);
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteCollectionDialog", (collectionToDelete) => {
  collection.value = collectionToDelete;
  show.value = true;
});

async function deleteCollection() {
  if (!collection.value) return;

  show.value = false;
  await collectionApi
    .deleteCollection({ collection: collection.value })
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      collectionsStore.remove(collection.value as Collection);
      if (collection.value?.name.toLowerCase() == "favourites") {
        collectionsStore.setFavCollection(undefined);
      }
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

  await router.push({ name: "dashboard" });

  collectionsStore.remove(collection.value);
  emitter?.emit("refreshDrawer", null);
  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <r-dialog
    v-if="collection"
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="lgAndUp ? '50vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center align-center pa-2" no-gutters>
        <span>Removing collection</span>
        <r-avatar class="ml-1" :collection="collection" />
        <span class="ml-1 text-romm-accent-1">{{ collection.name }}</span>
        <span class="ml-1">from RomM. Do you confirm?</span>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn class="bg-terciary text-romm-red" @click="deleteCollection">
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
