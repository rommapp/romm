<script setup lang="ts">
import type { EnhancedRomSchema, PlatformSchema } from "@/__generated__";
import VersionSwitcher from "@/components/Details/VersionSwitcher.vue";
import storeDownload from "@/stores/download";
import { formatBytes } from "@/utils";

defineProps<{ rom: EnhancedRomSchema; platform: PlatformSchema }>();
const downloadStore = storeDownload();
</script>
<template>
  <v-row
    v-if="rom?.sibling_roms && rom.sibling_roms.length > 0"
    class="align-center my-3"
    no-gutters
  >
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>Ver.</span>
    </v-col>
    <v-col>
      <version-switcher :rom="rom" :platform="platform" />
    </v-col>
  </v-row>
  <v-row v-if="!rom.multi" class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>File</span>
    </v-col>
    <v-col class="text-body-1">
      <span>{{ rom.file_name }}</span>
    </v-col>
  </v-row>
  <v-row v-if="rom.multi" class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
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
  <v-row class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>Size</span>
    </v-col>
    <v-col>
      <span>{{ formatBytes(rom.file_size_bytes) }}</span>
    </v-col>
  </v-row>
  <v-row v-if="rom.tags.length > 0" class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
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
  <v-row v-if="rom.genres.length > 0" class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>Genres</span>
    </v-col>
    <v-col>
      <v-chip
        v-for="{ id, name } in rom.genres"
        :key="id"
        class="my-1 mr-2"
        label
        variant="outlined"
      >
        {{ name }}
      </v-chip>
    </v-col>
  </v-row>
  <v-row v-if="rom.franchises.length > 0" class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>Franchises</span>
    </v-col>
    <v-col>
      <v-chip
        v-for="{ id, name } in rom.franchises"
        :key="id"
        class="my-1 mr-2"
        label
        variant="outlined"
      >
        {{ name }}
      </v-chip>
    </v-col>
  </v-row>
  <v-row v-if="rom.collections.length > 0" class="align-center my-3" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>Collections</span>
    </v-col>
    <v-col>
      <v-chip
        v-for="{ id, name } in rom.collections"
        :key="id"
        class="my-1 mr-2"
        label
        variant="outlined"
      >
        {{ name }}
      </v-chip>
    </v-col>
  </v-row>
  <v-row v-if="rom.companies.length > 0" class="align-center" no-gutters>
    <v-col cols="3" sm="3" md="2" xl="1">
      <span>Companies</span>
    </v-col>
    <v-col>
      <v-chip
        v-for="{ id, company } in rom.companies"
        :key="id"
        class="my-1 mr-2"
        label
        variant="outlined"
      >
        {{ company.name }}
      </v-chip>
    </v-col>
  </v-row>
  <v-divider class="mx-2 my-4" />
  <v-row no-gutters>
    <v-col class="text-caption">
      <p>{{ rom.summary }}</p>
    </v-col>
  </v-row>
</template>
