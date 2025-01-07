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

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const romsStore = storeRoms();
const collectionsStore = storeCollections();
const selectedCollection = ref<UpdatedCollection>();
const roms = ref<SimpleRom[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showAddToCollectionDialog", (romsToAdd) => {
  roms.value = romsToAdd;
  updateDataTablePages();
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
const page = ref(1);
const itemsPerPage = ref(10);
const pageCount = ref(0);
const PER_PAGE_OPTIONS = [10, 25, 50, 100];

async function addRomsToCollection() {
  if (!selectedCollection.value) return;
  selectedCollection.value.roms.push(...roms.value.map((r) => r.id));
  await collectionApi
    .updateCollection({ collection: selectedCollection.value })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: `Roms added to ${selectedCollection.value?.name} successfully!`,
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
      romsStore.resetSelection();
      closeDialog();
    });
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(roms.value.length / itemsPerPage.value);
}

watch(itemsPerPage, async () => {
  updateDataTablePages();
});

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
    icon="mdi-bookmark-plus-outline"
    scroll-content
    :width="mdAndUp ? '45vw' : '95vw'"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>{{ t("rom.adding-to-collection-part1") }}</span>
        <span class="text-romm-accent-1 mx-1">{{ roms.length }}</span>
        <span>{{ t("rom.adding-to-collection-part2") }}</span>
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
      <v-data-table
        :item-value="(item) => item.id"
        :items="roms"
        :width="mdAndUp ? '60vw' : '95vw'"
        :items-per-page="itemsPerPage"
        :items-per-page-options="PER_PAGE_OPTIONS"
        :headers="HEADERS"
        v-model:page="page"
        hide-default-header
      >
        <template #item.name="{ item }">
          <rom-list-item :rom="item" with-filename />
        </template>
        <template #bottom>
          <v-divider />
          <v-row no-gutters class="pt-2 align-center justify-center">
            <v-col class="px-6">
              <v-pagination
                v-model="page"
                rounded="0"
                :show-first-last-page="true"
                active-color="romm-accent-1"
                :length="pageCount"
              />
            </v-col>
            <v-col cols="5" sm="3">
              <v-select
                v-model="itemsPerPage"
                class="pa-2"
                label="Roms per page"
                density="compact"
                variant="outlined"
                :items="PER_PAGE_OPTIONS"
                hide-details
              />
            </v-col>
          </v-row>
        </template>
      </v-data-table>
    </template>
    <template #append>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog" variant="flat">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-terciary text-romm-green"
            :disabled="!selectedCollection"
            :variant="!selectedCollection ? 'plain' : 'flat'"
            @click="addRomsToCollection"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
