<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import RAvatarCollection from "@/components/common/Collection/RAvatar.vue";
import RDialog from "@/components/common/RDialog.vue";
import { ROUTES } from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import storeCollections, { type Collection } from "@/stores/collections";
import type { Events } from "@/types/emitter";

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

async function deleteCollection() {
  if (!collection.value) return;

  show.value = false;
  await collectionApi
    .deleteCollection({ collection: collection.value })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: "Collection deleted",
        icon: "mdi-check-bold",
        color: "green",
      });
      collectionsStore.removeCollection(collection.value as Collection);
      if (collection.value?.is_favorite) {
        collectionsStore.setFavoriteCollection(undefined);
      }
    })
    .catch((error) => {
      console.error(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });

  await router.push({ name: ROUTES.HOME });

  collectionsStore.removeCollection(collection.value);
  emitter?.emit("refreshDrawer", null);
  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <RDialog
    v-if="collection"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="lgAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-row class="justify-center align-center pa-2" no-gutters>
        <span>{{ t("collection.removing-collection-1") }}</span>
        <v-chip class="pl-0 ml-1" label>
          <RAvatarCollection :collection="collection" :size="35" class="mr-2" />
          {{ collection.name }}
        </v-chip>
        <span class="ml-1">{{ t("collection.removing-collection-2") }}</span>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-toplayer text-romm-red" @click="deleteCollection">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
