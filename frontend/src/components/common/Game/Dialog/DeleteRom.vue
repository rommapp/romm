<script setup lang="ts">
import RomListItem from "@/components/common/Game/ListItem.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import configApi from "@/services/api/config";
import type { Events } from "@/types/emitter";
import storeConfig from "@/stores/config";
import { ROUTES } from "@/plugins/router";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const router = useRouter();
const route = useRoute();
const show = ref(false);
const romsStore = storeRoms();
const roms = ref<SimpleRom[]>([]);
const romsToDeleteFromFs = ref<number[]>([]);
const excludeOnDelete = ref(false);
const platformId = ref<number>(0);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
emitter?.on("showDeleteRomDialog", (romsToDelete) => {
  roms.value = romsToDelete;
  platformId.value = roms.value[0].platform_id;
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

async function deleteRoms() {
  await romApi
    .deleteRoms({ roms: roms.value, deleteFromFs: romsToDeleteFromFs.value })
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      if (excludeOnDelete.value) {
        for (const rom of roms.value) {
          if (!rom.multi) {
            configApi.addExclusion({
              exclusionValue: rom.fs_name,
              exclusionType: "EXCLUDED_SINGLE_FILES",
            });
            configStore.addExclusion("EXCLUDED_SINGLE_FILES", rom.fs_name);
          } else {
            configApi.addExclusion({
              exclusionValue: rom.fs_name,
              exclusionType: "EXCLUDED_MULTI_FILES",
            });
            configStore.addExclusion("EXCLUDED_MULTI_FILES", rom.fs_name);
          }
        }
      }
      romsStore.resetSelection();
      romsStore.remove(roms.value);
      emitter?.emit("refreshDrawer", null);
      closeDialog();
      if (route.name == "rom") {
        router.push({
          name: ROUTES.PLATFORM,
          params: { platform: platformId.value },
        });
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
}

function closeDialog() {
  romsToDeleteFromFs.value = [];
  roms.value = [];
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
        <span class="text-primary mx-1">{{ roms.length }}</span>
        <span>games from RomM</span>
      </v-row>
    </template>
    <template #prepend>
      <v-list-item class="text-caption text-center">
        <span
          >Select the games you want to remove from your filesystem, otherwise
          they will only be deleted from RomM database.</span
        >
      </v-list-item>
    </template>
    <template #content>
      <v-data-table-virtual
        :item-value="(item) => item.id"
        :items="roms"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
        v-model="romsToDeleteFromFs"
        show-select
      >
        <template #item.name="{ item }">
          <rom-list-item :rom="item" with-filename with-size>
            <template #append-body>
              <v-row v-if="romsToDeleteFromFs.includes(item.id)" no-gutters>
                <v-col>
                  <v-chip label size="x-small" class="text-romm-red">
                    Removing from filesystem
                  </v-chip>
                </v-col>
              </v-row>
            </template>
          </rom-list-item>
        </template>
      </v-data-table-virtual>
    </template>
    <template #append>
      <v-row class="justify-center text-center pa-2" no-gutters>
        <v-col>
          <v-chip @click="excludeOnDelete = !excludeOnDelete" variant="text"
            ><v-icon :color="excludeOnDelete ? 'accent' : ''" class="mr-1">{{
              excludeOnDelete
                ? "mdi-checkbox-outline"
                : "mdi-checkbox-blank-outline"
            }}</v-icon>
            {{ t("common.exclude-on-delete") }}
          </v-chip>
        </v-col>
      </v-row>
      <v-row v-if="romsToDeleteFromFs.length > 0" no-gutters>
        <v-col>
          <v-list-item class="text-center mt-2">
            <span class="text-romm-red text-body-1">WARNING:</span>
            <span class="text-body-2 ml-1">You are going to remove</span>
            <span class="text-romm-red text-body-1 ml-1">{{
              romsToDeleteFromFs.length
            }}</span>
            <span class="text-body-2 ml-1"
              >roms from your filesystem. This action can't be reverted!</span
            >
          </v-list-item>
        </v-col>
      </v-row>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog" variant="flat">
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-red bg-toplayer"
            variant="flat"
            @click="deleteRoms"
          >
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
