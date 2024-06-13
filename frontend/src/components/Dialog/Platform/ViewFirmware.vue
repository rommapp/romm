<script setup lang="ts">
import type { FirmwareSchema } from "@/__generated__";
import AddFirmwareDialog from "@/components/Dialog/Platform/AddFirmware.vue";
import RDialog from "@/components/common/Dialog.vue";
import firmwareApi from "@/services/api/firmware";
import { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs, mdAndUp, lgAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const platform = ref<Platform | null>(null);
const selectedFirmware = ref<FirmwareSchema[]>([]);
const firmwaresToDeleteFromFs = ref<number[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showFirmwareDialog", (selectedPlatform) => {
  platform.value = selectedPlatform;
  updateDataTablePages();
  show.value = true;
});
const HEADERS = [
  {
    title: "Firmware",
    align: "start",
    sortable: true,
    key: "name",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;
const firmwarePage = ref(1);
const firmwarePerPage = ref(10);
const firmwarePageCount = ref(0);
const PER_PAGE_OPTIONS = [10, 25, 50, 100];

// Functions
// TODO: add delete from fs
function deleteFirmware(firmware: FirmwareSchema, deleteFromFs: number[] = []) {
  firmwareApi
    .deleteFirmware({ firmware: [firmware], deleteFromFs: deleteFromFs })
    .then(() => {
      if (platform.value) {
        platform.value.firmware = platform.value.firmware?.filter(
          (firm) => firm.id == firmware.id
        );
      }
      emitter?.emit("snackbarShow", {
        msg: "Firmware deleted successfully!",
        icon: "mdi-check-circle",
        color: "green",
        timeout: 4000,
      });
    });
}

function closeDialog() {
  show.value = false;
  platform.value = null;
}

function updateDataTablePages() {
  firmwarePageCount.value = Math.ceil(
    Number(platform.value?.firmware?.length) / firmwarePerPage.value
  );
}
watch(firmwarePerPage, async () => {
  updateDataTablePages();
});
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-memory"
    empty-state-type="firmware"
    scroll-content
    :width="mdAndUp ? '65vw' : '95vw'"
  >
    <template #content>
      <v-data-table
        v-if="platform?.firmware"
        :item-value="(item) => item.file_name"
        :items="platform?.firmware ?? []"
        :width="mdAndUp ? '60vw' : '95vw'"
        :items-per-page="firmwarePerPage"
        :items-per-page-options="PER_PAGE_OPTIONS"
        :headers="HEADERS"
        v-model:page="firmwarePage"
        show-select
      >
        <template #header.actions>
          <v-btn
            prepend-icon="mdi-plus"
            class="text-romm-accent-1"
            variant="outlined"
            @click="emitter?.emit('addFirmwareDialog', platform as Platform)"
          >
            Add
          </v-btn>
        </template>
        <template #item.name="{ item }">
          <v-list-item class="px-0">
            <v-row no-gutters>
              <v-col>
                <span>{{ item.file_name }}</span>
              </v-col>
            </v-row>
            <v-row no-gutters v-if="!mdAndUp">
              <v-col>
                <v-chip size="x-small" label>{{
                  formatBytes(item.file_size_bytes)
                }}</v-chip>
              </v-col>
            </v-row>
            <v-row v-if="!lgAndUp" no-gutters>
              <v-col>
                <v-chip color="blue" size="x-small" label
                  ><span class="text-truncate">
                    {{ item.md5_hash }}</span
                  ></v-chip
                >
                <v-chip
                  label
                  v-if="item.is_verified"
                  prepend-icon="mdi-check"
                  size="x-small"
                  class="text-romm-green"
                  :class="{ 'ml-1': !xs }"
                  title="Passed file size, SHA1 and MD5 checksum checks"
                  ><span>Verified</span>
                </v-chip>
              </v-col>
            </v-row>
            <template> </template>
            <template #append>
              <template v-if="lgAndUp">
                <v-chip color="blue" size="x-small" label
                  ><span class="text-truncate">
                    {{ item.md5_hash }}</span
                  ></v-chip
                >
                <v-chip
                  label
                  v-if="item.is_verified"
                  prepend-icon="mdi-check"
                  size="x-small"
                  class="text-romm-green ml-2"
                  title="Passed file size, SHA1 and MD5 checksum checks"
                  ><span>Verified</span>
                </v-chip>
              </template>
              <v-chip v-if="mdAndUp" class="ml-2" size="x-small" label>{{
                formatBytes(item.file_size_bytes)
              }}</v-chip>
            </template>
          </v-list-item>
        </template>
        <template #no-data
          ><span>No firmware found for {{ platform.name }}</span></template
        >
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact">
            <v-btn
              :href="`/api/firmware/${item.id}/content/${item.file_name}`"
              download
              size="small"
            >
              <v-icon> mdi-download </v-icon>
            </v-btn>
            <v-btn size="small" @click="deleteFirmware(item)">
              <v-icon class="text-romm-red">mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </template>
        <template #bottom>
          <v-divider />
          <v-row no-gutters class="pt-2 align-center justify-center">
            <v-col class="px-6">
              <v-pagination
                v-model="firmwarePage"
                rounded="0"
                :show-first-last-page="true"
                active-color="romm-accent-1"
                :length="firmwarePageCount"
              />
            </v-col>
            <v-col cols="5" sm="3" xl="2">
              <v-select
                v-model="firmwarePerPage"
                class="pa-2"
                label="Files per page"
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
  </r-dialog>

  <add-firmware-dialog />
</template>
