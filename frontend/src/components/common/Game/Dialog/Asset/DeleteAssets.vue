<script setup lang="ts">
import type { SaveSchema, StateSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndUp, smAndUp } = useDisplay();
const romsStore = storeRoms();
const show = ref(false);
const assetType = ref<"user_saves" | "user_states">("user_saves");
const romRef = ref<DetailedRom | null>(null);
const assets = ref<(SaveSchema | StateSchema)[]>([]);
const assetsToDeleteFromFs = ref<number[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteSavesDialog", ({ rom, saves }) => {
  assetType.value = "user_saves";
  assets.value = saves;
  romRef.value = rom;
  updateDataTablePages();
  show.value = true;
});
emitter?.on("showDeleteStatesDialog", ({ rom, states }) => {
  assetType.value = "user_states";
  assets.value = states;
  romRef.value = rom;
  updateDataTablePages();
  show.value = true;
});
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "file_name",
  },
] as const;
const page = ref(1);
const itemsPerPage = ref(10);
const pageCount = ref(0);
const PER_PAGE_OPTIONS = [10, 25, 50, 100];
const assetsNameMapping = { user_saves: "saves", user_states: "states" };

// Funtcions
// TODO: make remove assets reactive
async function deleteAssets() {
  if (!assets.value) return;

  const result =
    assetType.value === "user_saves"
      ? saveApi.deleteSaves({
          saves: assets.value,
          deleteFromFs: assetsToDeleteFromFs.value,
        })
      : stateApi.deleteStates({
          states: assets.value,
          deleteFromFs: assetsToDeleteFromFs.value,
        });

  result
    .then(() => {
      if (romRef.value?.[assetType.value]) {
        const deletedAssetIds = assets.value.map((asset) => asset.id);
        romRef.value[assetType.value] =
          romRef.value[assetType.value]?.filter(
            (asset) => !deletedAssetIds.includes(asset.id)
          ) ?? [];
        romsStore.update(romRef.value);
        emitter?.emit("romUpdated", romRef.value);
      }
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to delete ${assetsNameMapping[assetType.value]}: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      closeDialog();
    });
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(assets.value.length / itemsPerPage.value);
}

watch(itemsPerPage, async () => {
  updateDataTablePages();
});

function closeDialog() {
  assetsToDeleteFromFs.value = [];
  assets.value = [];
  show.value = false;
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>Removing</span>
        <span class="text-romm-accent-1 mx-1">{{ assets.length }}</span>
        <span>{{ assetType.slice(5) }} of</span>
        <span class="text-romm-accent-1 mx-1">{{ romRef?.name }}</span>
        <span>from RomM</span>
      </v-row>
    </template>
    <template #prepend>
      <v-list-item class="text-caption text-center">
        <span
          >Select the {{ assetType.slice(5) }} you want to remove from your
          filesystem, otherwise they will only be deleted from RomM
          database.</span
        >
      </v-list-item>
    </template>
    <template #content>
      <v-data-table
        :item-value="(item) => item.id"
        :items="assets"
        :width="mdAndUp ? '60vw' : '95vw'"
        :items-per-page="itemsPerPage"
        :items-per-page-options="PER_PAGE_OPTIONS"
        :headers="HEADERS"
        v-model="assetsToDeleteFromFs"
        v-model:page="page"
        show-select
      >
        <template #item.file_name="{ item }">
          <v-list-item class="px-0">
            <v-row no-gutters>
              <v-col>
                {{ item.file_name }}<v-chip
                  v-if="assetsToDeleteFromFs.includes(item.id) && smAndUp"
                  label
                  size="x-small"
                  class="text-romm-red ml-1"
                >
                  Removing from filesystem
                </v-chip>
              </v-col>
            </v-row>
            <v-row no-gutters>
              <v-col>
                <template v-if="!smAndUp">
                  <v-chip size="x-small" label
                    >{{ formatBytes(item.file_size_bytes) }}
                  </v-chip>
                  <v-chip
                    v-if="item.emulator"
                    size="x-small"
                    class="ml-1 text-orange"
                    label
                    >{{ item.emulator }}
                  </v-chip>
                </template>
                <v-chip
                  v-if="assetsToDeleteFromFs.includes(item.id) && !smAndUp"
                  label
                  size="x-small"
                  class="text-romm-red"
                >
                  Removing from filesystem
                </v-chip>
              </v-col>
            </v-row>
            <template #append>
              <template v-if="smAndUp">
                <v-chip
                  v-if="item.emulator"
                  size="x-small"
                  class="text-orange"
                  label
                  >{{ item.emulator }}
                </v-chip>
                <v-chip class="ml-1" size="x-small" label
                  >{{ formatBytes(item.file_size_bytes) }}
                </v-chip>
              </template>
            </template>
          </v-list-item>
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
            <v-col cols="5" sm="3" xl="2">
              <v-select
                v-model="itemsPerPage"
                class="pa-2"
                label="Assets per page"
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
      <v-row v-if="assetsToDeleteFromFs.length > 0" no-gutters>
        <v-col>
          <v-list-item class="text-center mt-2">
            <span class="text-romm-red text-body-1">WARNING:</span>
            <span class="text-body-2 ml-1">You are going to remove</span>
            <span class="text-romm-red text-body-1 ml-1">{{
              assetsToDeleteFromFs.length
            }}</span>
            <span class="text-body-2 ml-1"
              >{{ assetType.slice(5) }} from your filesystem. This action can't
              be reverted!</span
            >
          </v-list-item>
        </v-col>
      </v-row>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog" variant="flat">
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-red bg-terciary"
            variant="flat"
            @click="deleteAssets"
          >
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
