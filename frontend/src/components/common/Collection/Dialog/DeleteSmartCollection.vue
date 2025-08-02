<script setup lang="ts">
import RAvatarCollection from "@/components/common/Collection/RAvatar.vue";
import RDialog from "@/components/common/RDialog.vue";
import collectionApi from "@/services/api/collection";
import storeCollections, { type SmartCollection } from "@/stores/collections";
import type { Events } from "@/types/emitter";
import { ROUTES } from "@/plugins/router";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const router = useRouter();
const { lgAndUp } = useDisplay();
const collectionsStore = storeCollections();
const smartCollection = ref<SmartCollection | null>(null);
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteSmartCollectionDialog", (smartCollectionToDelete) => {
  smartCollection.value = smartCollectionToDelete;
  show.value = true;
});

async function deleteSmartCollection() {
  if (!smartCollection.value) return;

  await collectionApi
    .deleteSmartCollection(smartCollection.value.id)
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });

      if (!smartCollection.value) return;
      collectionsStore.removeSmartCollection(smartCollection.value);
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
    .finally(async () => {
      smartCollection.value = null;

      emitter?.emit("refreshDrawer", null);
      await router.push({ name: ROUTES.HOME });

      closeDialog();
    });
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <r-dialog
    v-if="smartCollection"
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="lgAndUp ? '50vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center align-center pa-2" no-gutters>
        <span>{{ t("collection.removing-smart-collection-1") }}</span>
        <v-chip class="pl-0 ml-1" label>
          <r-avatar-collection
            :collection="smartCollection"
            :size="35"
            class="mr-2"
          />
          {{ smartCollection.name }}
        </v-chip>
        <span class="ml-1">{{
          t("collection.removing-smart-collection-2")
        }}</span>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-red"
            @click="deleteSmartCollection"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
