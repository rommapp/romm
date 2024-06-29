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

// Props
const props = defineProps<{ rom: DetailedRom; platform: Platform }>();
const emitter = inject<Emitter<Events>>("emitter");
const downloadStore = storeDownload();

// Functions
async function updateMainSibling() {
  const updatedRom = props.rom;
  // updatedRom.fav_sibling = !props.rom.fav_sibling;
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
  <v-row no-gutters>
    <v-col>
      <v-row
        v-if="rom.sibling_roms && rom.sibling_roms.length > 0"
        class="align-center my-3"
        no-gutters
      >
        <v-col cols="3" xl="2">
          <span>Version</span>
        </v-col>
        <v-col>
          <v-row class="align-center" no-gutters>
            <version-switcher :rom="rom" :platform="platform" />
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Set as default version"
              open-delay="300"
            >
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  variant="flat"
                  rounded="0"
                  size="small"
                  @click="updateMainSibling"
                  ><v-icon
                    :class="rom.fav_sibling ? '' : 'mr-1'"
                    :color="rom.fav_sibling ? 'romm-accent-1' : ''"
                    >{{
                      rom.fav_sibling
                        ? "mdi-checkbox-outline"
                        : "mdi-checkbox-blank-outline"
                    }}</v-icon
                  >{{ rom.fav_sibling ? "" : "Default" }}</v-btn
                >
              </template></v-tooltip
            >
          </v-row>
        </v-col>
      </v-row>
      <v-row v-if="!rom.multi" class="align-center my-3" no-gutters>
        <v-col cols="3" xl="2">
          <span>File</span>
        </v-col>
        <v-col>
          <span class="text-body-1">{{ rom.file_name }}</span>
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
            rounded="0"
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
      <v-row no-gutters class="align-center my-3">
        <v-col cols="3" xl="2">
          <span>Size</span>
        </v-col>
        <v-col>
          <v-chip size="small" label>{{
            formatBytes(rom.file_size_bytes)
          }}</v-chip>
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
            size="small"
            class="mr-2"
            label
            color="romm-accent-1"
            variant="tonal"
          >
            {{ tag }}
          </v-chip>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>
