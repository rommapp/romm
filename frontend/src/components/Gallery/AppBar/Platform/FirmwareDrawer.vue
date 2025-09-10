<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import type { FirmwareSchema } from "@/__generated__";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import DeleteFirmwareDialog from "@/components/common/Platform/Dialog/DeleteFirmware.vue";
import UploadFirmwareDialog from "@/components/common/Platform/Dialog/UploadFirmware.vue";
import storeAuth from "@/stores/auth";
import storeGalleryView from "@/stores/galleryView";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, calculateMainLayoutWidth } from "@/utils";

const { t } = useI18n();
const { xs, mdAndUp } = useDisplay();
const auth = storeAuth();
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const galleryViewStore = storeGalleryView();
const { activeFirmwareDrawer } = storeToRefs(galleryViewStore);
const { calculatedWidth } = calculateMainLayoutWidth();
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
const tabIndex = computed(() => (activeFirmwareDrawer.value ? 0 : -1));

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
</script>

<template>
  <v-navigation-drawer
    v-model="activeFirmwareDrawer"
    mobile
    floating
    location="bottom"
    :class="{
      'my-2 px-1 max-h-50': activeFirmwareDrawer,
    }"
    class="bg-surface border-0 rounded mx-2 px-1"
    :style="{
      width: calculatedWidth,
    }"
    tabindex="-1"
  >
    <v-data-table-virtual
      v-model="selectedFirmware"
      :items="currentPlatform?.firmware ?? []"
      :width="mdAndUp ? '60vw' : '95vw'"
      :headers="HEADERS"
      return-object
      show-select
      tabindex="-1"
    >
      <template #header.actions>
        <v-btn-group tabindex="-1" divided density="compact">
          <v-btn
            v-if="auth.scopes.includes('platforms.write')"
            size="small"
            :tabindex="tabIndex"
            @click="emitter?.emit('addFirmwareDialog', null)"
          >
            <v-icon>mdi-cloud-upload-outline</v-icon>
          </v-btn>
          <v-btn
            :disabled="!selectedFirmware.length"
            size="small"
            :tabindex="tabIndex"
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
            :tabindex="tabIndex"
            :variant="selectedFirmware.length > 0 ? 'flat' : 'plain'"
            @click="deleteSelectedFirmware"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </v-btn-group>
      </template>
      <template #item.name="{ item }">
        <v-list-item :tabindex="tabIndex" role="listitem" class="px-0">
          <v-row no-gutters>
            <v-col>
              <MissingFromFSIcon
                v-if="item.missing_from_fs"
                class="mr-1"
                text="Missing firmware from filesystem"
              />
              <span>{{ item.file_name }}</span>
            </v-col>
          </v-row>
          <v-row v-if="!mdAndUp" no-gutters>
            <v-col>
              <v-chip size="x-small" tabindex="-1" label>
                {{ formatBytes(item.file_size_bytes) }}
              </v-chip>
              <v-chip
                color="blue"
                size="x-small"
                tabindex="-1"
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
                tabindex="-1"
                class="text-romm-green"
                :class="{ 'ml-1': !xs }"
                title="Passed file size, SHA1 and MD5 checksum checks"
              >
                <span>Verified</span>
              </v-chip>
            </v-col>
          </v-row>
          <template #append>
            <template v-if="mdAndUp">
              <v-chip size="x-small" tabindex="-1" label>
                {{ formatBytes(item.file_size_bytes) }}
              </v-chip>
              <v-chip
                class="ml-1"
                color="blue"
                size="x-small"
                tabindex="-1"
                label
              >
                <span class="text-truncate">{{ item.md5_hash }}</span>
              </v-chip>
              <v-chip
                v-if="item.is_verified"
                label
                prepend-icon="mdi-check"
                size="x-small"
                tabindex="-1"
                class="text-romm-green ml-1"
                title="Passed file size, SHA1 and MD5 checksum checks"
              >
                <span>Verified</span>
              </v-chip>
            </template>
          </template>
        </v-list-item>
      </template>
      <template #no-data>
        <span>{{ t("platform.no-firmware-found") }}</span>
      </template>
      <template #item.actions="{ item }">
        <v-btn-group tabindex="-1" divided density="compact">
          <v-btn
            :href="`/api/firmware/${item.id}/content/${item.file_name}`"
            download
            size="small"
            :tabindex="tabIndex"
          >
            <v-icon> mdi-download </v-icon>
          </v-btn>
          <v-btn
            v-if="auth.scopes.includes('platforms.write')"
            size="small"
            :tabindex="tabIndex"
            @click="emitter?.emit('showDeleteFirmwareDialog', [item])"
          >
            <v-icon class="text-romm-red"> mdi-delete </v-icon>
          </v-btn>
        </v-btn-group>
      </template>
    </v-data-table-virtual>
  </v-navigation-drawer>
  <UploadFirmwareDialog />
  <DeleteFirmwareDialog />
</template>
