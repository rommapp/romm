<script setup lang="ts">
import type { FirmwareSchema } from "@/__generated__";
import DeleteFirmwareDialog from "@/components/common/Platform/Dialog/DeleteFirmware.vue";
import UploadFirmwareDialog from "@/components/common/Platform/Dialog/UploadFirmware.vue";
import storeAuth from "@/stores/auth";
import storeGalleryView from "@/stores/galleryView";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, watch, onMounted } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { xs, mdAndUp } = useDisplay();
const auth = storeAuth();
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const galleryViewStore = storeGalleryView();
const { activeFirmwareDrawer } = storeToRefs(galleryViewStore);
const selectedFirmware = ref<FirmwareSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
const HEADERS = [
  {
    title: "Firmware",
    align: "start",
    sortable: true,
    key: "name",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;
const page = ref(1);
const itemsPerPage = ref(5);
const pageCount = ref(0);
const PER_PAGE_OPTIONS = [5, 10, 25];

// Functions
function downloadSelectedFirmware() {
  selectedFirmware.value.map((firmware) => {
    const a = document.createElement("a");
    a.href = `/api/firmware/${firmware.id}/content/${firmware.file_name}`;
    a.download = `${firmware.file_name}`;
    a.click();
  });
  selectedFirmware.value = [];
}

function deleteSelectedFirmware() {
  emitter?.emit("showDeleteFirmwareDialog", selectedFirmware.value);
  selectedFirmware.value = [];
}

function updateDataTablePages() {
  if (currentPlatform.value?.firmware) {
    pageCount.value = Math.ceil(
      Number(currentPlatform.value.firmware.length) / itemsPerPage.value,
    );
  }
}

watch(itemsPerPage, async () => {
  updateDataTablePages();
});

onMounted(() => {
  updateDataTablePages();
});
</script>

<template>
  <v-navigation-drawer
    v-model="activeFirmwareDrawer"
    mobile
    floating
    location="bottom"
  >
    <v-data-table
      :items="currentPlatform?.firmware ?? []"
      :width="mdAndUp ? '60vw' : '95vw'"
      :items-per-page="itemsPerPage"
      :items-per-page-options="PER_PAGE_OPTIONS"
      :headers="HEADERS"
      v-model="selectedFirmware"
      v-model:page="page"
      return-object
      show-select
    >
      <template #header.actions>
        <v-btn-group divided density="compact">
          <v-btn
            v-if="auth.scopes.includes('platforms.write')"
            size="small"
            @click="emitter?.emit('addFirmwareDialog', null)"
          >
            <v-icon>mdi-upload</v-icon>
          </v-btn>
          <v-btn
            :disabled="!selectedFirmware.length"
            size="small"
            :variant="selectedFirmware.length > 0 ? 'flat' : 'plain'"
            @click="downloadSelectedFirmware"
          >
            <v-icon>mdi-download</v-icon>
          </v-btn>
          <v-btn
            v-if="auth.scopes.includes('platforms.write')"
            :class="{
              'text-romm-red': selectedFirmware.length,
            }"
            :disabled="!selectedFirmware.length"
            size="small"
            :variant="selectedFirmware.length > 0 ? 'flat' : 'plain'"
            @click="deleteSelectedFirmware"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </v-btn-group>
      </template>
      <template #item.name="{ item }">
        <v-list-item class="px-0">
          <v-row no-gutters>
            <v-col>
              <span>{{ item.file_name }}</span>
            </v-col>
          </v-row>
          <v-row v-if="!mdAndUp" no-gutters>
            <v-col>
              <v-chip size="x-small" label>{{
                formatBytes(item.file_size_bytes)
              }}</v-chip>
              <v-chip
                color="blue"
                size="x-small"
                label
                :class="{ 'ml-1': !xs }"
              >
                <span class="text-truncate"> {{ item.md5_hash }}</span>
              </v-chip>
              <v-chip
                v-if="item.is_verified"
                label
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
            <template v-if="mdAndUp">
              <v-chip size="x-small" label>{{
                formatBytes(item.file_size_bytes)
              }}</v-chip>
              <v-chip class="ml-1" color="blue" size="x-small" label>
                <span class="text-truncate">{{ item.md5_hash }}</span>
              </v-chip>
              <v-chip
                v-if="item.is_verified"
                label
                prepend-icon="mdi-check"
                size="x-small"
                class="text-romm-green ml-1"
                title="Passed file size, SHA1 and MD5 checksum checks"
                ><span>Verified</span>
              </v-chip>
            </template>
          </template>
        </v-list-item>
      </template>
      <template #no-data
        ><span>{{ t("platform.no-firmware-found") }}</span></template
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
          <v-btn
            v-if="auth.scopes.includes('platforms.write')"
            size="small"
            @click="emitter?.emit('showDeleteFirmwareDialog', [item])"
          >
            <v-icon class="text-romm-red">mdi-delete</v-icon>
          </v-btn>
        </v-btn-group>
      </template>
      <template #bottom>
        <v-divider />
        <v-row no-gutters class="pa-1 align-center justify-center">
          <v-col cols="8" sm="9" md="10" class="px-3">
            <v-pagination
              :show-first-last-page="!xs"
              v-model="page"
              rounded="0"
              active-color="romm-accent-1"
              :length="pageCount"
            />
          </v-col>
          <v-col>
            <v-select
              v-model="itemsPerPage"
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
  </v-navigation-drawer>
  <upload-firmware-dialog />
  <delete-firmware-dialog />
</template>
