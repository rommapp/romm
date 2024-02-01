<script setup lang="ts">
import type { EnhancedRomSchema, PlatformSchema } from "@/__generated__";
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import storeDownload from "@/stores/download";
import { formatBytes } from "@/utils";

defineProps<{ rom: EnhancedRomSchema, platform: PlatformSchema }>();
const downloadStore = storeDownload();
</script>
<template>
  <v-row
    v-if="rom?.sibling_roms && rom.sibling_roms.length > 0"
    class="align-center py-2"
    no-gutters
  >
    <v-col cols="3" sm="2" xl="1">
      <span>Ver.</span>
    </v-col>
    <v-col>
      <version-switcher :rom="rom" :platform="platform" />
    </v-col>
  </v-row>
  <v-row v-if="!rom.multi" class="align-center py-2" no-gutters>
    <v-col cols="3" sm="2" xl="1">
      <span>File</span>
    </v-col>
    <v-col class="text-body-1">
      <span>{{ rom.file_name }}</span>
    </v-col>
  </v-row>
  <v-row v-if="rom.multi" class="align-center py-2" no-gutters>
    <v-col cols="3" sm="2" xl="1">
      <span>Files</span>
    </v-col>
    <v-col>
      <v-select
        :label="rom.file_name"
        item-title="file_name"
        v-model="downloadStore.filesToDownloadMultiFileRom"
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
  <v-row class="align-center py-2" no-gutters>
    <v-col cols="3" sm="2" xl="1">
      <span>Size</span>
    </v-col>
    <v-col>
      <span>{{ formatBytes(rom.file_size_bytes) }}</span>
    </v-col>
  </v-row>
  <v-row v-if="rom.igdb_id" class="align-center py-2" no-gutters>
    <v-col cols="3" sm="2" xl="1">
      <span>IGDB</span>
    </v-col>
    <v-col>
      <v-chip
        variant="outlined"
        class="text-romm-accent-1"
        label
      >
        <a style="text-decoration: none; color: inherit" :href="`https://www.igdb.com/games/${rom.slug}`" target="_blank">{{ rom.igdb_id }}</a>
      </v-chip>
    </v-col>
  </v-row>
  <v-row v-if="rom.tags.length > 0" class="align-center py-2" no-gutters>
    <v-col cols="3" sm="2" xl="1">
      <span>Tags</span>
    </v-col>
    <v-col>
      <v-chip-group class="pt-0">
        <v-chip v-for="tag in rom.tags" :key="tag" class="bg-chip" label>
          {{ tag }}
        </v-chip>
      </v-chip-group>
    </v-col>
  </v-row>
  <v-row class="py-3" no-gutters>
    <v-col class="text-caption">
      <p>{{ rom.summary }}</p>
    </v-col>
  </v-row>
</template>
