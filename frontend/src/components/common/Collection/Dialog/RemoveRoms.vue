<script setup lang="ts">
import RAvatarCollection from "@/components/common/Collection/RAvatar.vue";
import CollectionListItem from "@/components/common/Collection/ListItem.vue";
import RomListItem from "@/components/common/Game/ListItem.vue";
import RDialog from "@/components/common/RDialog.vue";
import type { UpdatedCollection } from "@/services/api/collection";
import collectionApi from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const romsStore = storeRoms();
const collectionsStore = storeCollections();
const selectedCollection = ref<UpdatedCollection>();
const roms = ref<SimpleRom[]>([]);
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showRemoveFromCollectionDialog", (romsToRemove) => {
  roms.value = romsToRemove;
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
  selectedCollection.value.rom_ids = selectedCollection.value.rom_ids.filter(
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
      emitter?.emit("refreshDrawer", null);
      collectionsStore.updateCollection(data);
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
      if (selectedCollection.value?.rom_ids.length == 0) {
        router.push({ name: ROUTES.HOME });
      }
      closeDialog();
    });
  closeDialog();
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
        <span>{{ t("rom.removing-from-collection-part1") }}</span>
        <span class="text-primary mx-1">{{ roms.length }}</span>
        <span>{{ t("rom.removing-from-collection-part2") }}</span>
      </v-row>
    </template>
    <template #prepend>
      <v-autocomplete
        v-model="selectedCollection"
        class="pa-3"
        density="default"
        :label="t('common.collection')"
        item-title="name"
        :items="collectionsStore.allCollections"
        variant="outlined"
        hide-details
        return-object
        clearable
      >
        <template #item="{ props, item }">
          <collection-list-item
            :collection="item.raw"
            v-bind="props"
            :with-title="false"
          />
        </template>
        <template #chip="{ item }">
          <v-chip class="pl-0" label>
            <r-avatar-collection
              :collection="item.raw"
              :size="35"
              class="mr-2"
            />
            {{ item.raw.name }}
          </v-chip>
        </template>
      </v-autocomplete>
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
            :disabled="!selectedCollection"
            class="bg-toplayer text-romm-red"
            :variant="!selectedCollection ? 'plain' : 'flat'"
            @click="removeRomsFromCollection"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
