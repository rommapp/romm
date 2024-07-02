<script setup lang="ts">
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeDownload from "@/stores/download";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import { ref, watch } from "vue";

// Props
const props = defineProps<{ rom: DetailedRom; platform: Platform }>();
const downloadStore = storeDownload();
const auth = storeAuth();
const romUser = ref(
  props.rom.rom_user ?? {
    id: null,
    user_id: auth.user?.id,
    rom_id: props.rom.id,
    updated_at: new Date(),
    note_raw_markdown: "",
    note_is_public: false,
    is_main_sibling: false,
  }
);

// Functions
async function toggleMainSibling() {
  ownProps.value.is_main_sibling = !ownProps.value.is_main_sibling;
  romApi.updateUserRomProps({
    romId: props.rom.id,
    noteRawMarkdown: ownProps.value.note_raw_markdown,
    noteIsPublic: ownProps.value.note_is_public,
    isMainSibling: ownProps.value.is_main_sibling,
  });
}

watch(
  () => props.rom,
  async () => {
    ownProps.value = props.rom.rom_user ?? {
      id: null,
      user_id: auth.user?.id,
      rom_id: props.rom.id,
      updated_at: new Date(),
      note_raw_markdown: "",
      note_is_public: false,
      is_main_sibling: false,
    };
  }
);
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
                  @click="toggleMainSibling"
                  ><v-icon
                    :class="ownProps.is_main_sibling ? '' : 'mr-1'"
                    :color="ownProps.is_main_sibling ? 'romm-accent-1' : ''"
                    >{{
                      ownProps.is_main_sibling
                        ? "mdi-checkbox-outline"
                        : "mdi-checkbox-blank-outline"
                    }}</v-icon
                  >{{ ownProps.is_main_sibling ? "" : "Default" }}</v-btn
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
