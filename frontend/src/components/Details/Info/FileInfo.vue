<script setup lang="ts">
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject } from "vue";

const props = defineProps<{ rom: DetailedRom; platform: Platform }>();
const emitter = inject<Emitter<Events>>("emitter");
const downloadStore = storeDownload();

async function updateMainSibling() {
  const updatedRom = props.rom;
  updatedRom.fav_sibling = !props.rom.fav_sibling;
  await romApi
    .updateRom({ rom: updatedRom })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Rom updated successfully!",
        icon: "mdi-check-bold",
        color: "green",
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}
</script>
<template>
  <v-row
    v-if="rom.sibling_roms && rom.sibling_roms.length > 0"
    class="align-center my-3"
    no-gutters
  >
    <v-col cols="3" xl="2">
      <span>Ver.</span>
    </v-col>
    <v-col>
      <v-row class="align-center" no-gutters>
        <version-switcher :rom="rom" :platform="platform" />
        <v-tooltip
          location="top"
          class="tooltip"
          transition="fade-transition"
          text="Set as main sibling"
          open-delay="300"
        >
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              @click="updateMainSibling"
              class="ml-4"
              icon
              density="comfortable"
              :ripple="false"
              color="secondary"
              variant="flat"
            >
              <v-icon color="romm-accent-1">{{
                rom.fav_sibling ? "mdi-star" : "mdi-star-outline"
              }}</v-icon>
            </v-btn>
          </template></v-tooltip
        >
      </v-row>
    </v-col>
  </v-row>
  <v-row v-if="!rom.multi" class="align-center my-3" no-gutters>
    <v-col cols="3" xl="2">
      <span>File</span>
    </v-col>
    <v-col class="text-body-1">
      <span>{{ rom.file_name }}</span>
    </v-col>
  </v-row>
  <v-row v-if="rom.multi" class="align-center my-3" no-gutters>
    <v-col cols="3" xl="2">
      <span>Files</span>
    </v-col>
    <v-col>
      <v-select
        v-model="downloadStore.filesToDownloadMultiFileRom"
        :label="rom.file_name"
        item-title="file_name"
        :items="rom.files"
        class="my-2"
        density="compact"
        variant="outlined"
        return-object
        multiple
        hide-details
        clearable
        chips
      />
    </v-col>
  </v-row>
  <v-row class="align-center my-3" no-gutters>
    <v-col cols="3" xl="2">
      <span>Size</span>
    </v-col>
    <v-col>
      <span>{{ formatBytes(rom.file_size_bytes) }}</span>
    </v-col>
  </v-row>
  <v-row v-if="rom.tags.length > 0" class="align-center my-3" no-gutters>
    <v-col cols="3" xl="2">
      <span>Tags</span>
    </v-col>
    <v-col>
      <v-chip
        v-for="tag in rom.tags"
        :key="tag"
        class="mr-2 py-1"
        label
        variant="outlined"
      >
        {{ tag }}
      </v-chip>
    </v-col>
  </v-row>
</template>
