<script setup lang="ts">
import RAvatarCollection from "@/components/common/Collection/RAvatar.vue";
import RDialog from "@/components/common/RDialog.vue";
import collectionApi from "@/services/api/collection";
import storeCollections, { type Collection } from "@/stores/collections";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
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

// Functions
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

  await router.push({ name: "home" });

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
        <span>{{ t("collection.removing-collection-1") }}</span>
        <v-chip class="pl-0 ml-1" label>
          <r-avatar-collection
            :collection="collection"
            :size="35"
            class="mr-2"
          />
          {{ collection.name }}
        </v-chip>
        <span class="ml-1">{{ t("collection.removing-collection-2") }}</span>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-terciary text-romm-red" @click="deleteCollection">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
