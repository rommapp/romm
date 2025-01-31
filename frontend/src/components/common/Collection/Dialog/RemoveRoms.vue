<script setup lang="ts">
import RomListItem from "@/components/common/Game/ListItem.vue";
import RDialog from "@/components/common/RDialog.vue";
import router from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import type { Collection } from "@/stores/collections";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const romsStore = storeRoms();
const selectedCollection = ref<Collection>();
const roms = ref<SimpleRom[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showRemoveFromCollectionDialog", (romsToRemove) => {
  roms.value = romsToRemove;
  selectedCollection.value = romsStore.currentCollection as Collection;
  show.value = true;
});
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
] as const;

async function removeRomsFromCollection() {
  if (!selectedCollection.value) return;
  selectedCollection.value.roms = selectedCollection.value.roms.filter(
    (id) => !roms.value.map((r) => r.id).includes(id),
  );
  await collectionApi
    .updateCollection({ collection: selectedCollection.value })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: `Roms removed from ${selectedCollection.value?.name} successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
      romsStore.remove(roms.value);
      emitter?.emit("refreshDrawer", null);
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
      romsStore.resetSelection();
      if (selectedCollection.value?.roms.length == 0) {
        router.push({ name: "home" });
      }
      closeDialog();
    });
}

function closeDialog() {
  roms.value = [];
  show.value = false;
  selectedCollection.value = undefined;
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-bookmark-remove-outline"
    scroll-content
    :width="mdAndUp ? '45vw' : '95vw'"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>{{ t("rom.remove-from-collection-part1") }}</span>
        <span class="text-primary mx-1">{{ roms.length }}</span>
        <span>{{ t("rom.remove-from-collection-part2") }}</span>
      </v-row>
    </template>
    <template #content>
      <v-data-table-virtual
        :item-value="(item) => item.id"
        :items="roms"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
        hide-default-header
      >
        <template #item.name="{ item }">
          <rom-list-item :rom="item" with-filename with-size />
        </template>
      </v-data-table-virtual>
    </template>
    <template #append>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog" variant="flat">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-red"
            variant="flat"
            @click="removeRomsFromCollection"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
