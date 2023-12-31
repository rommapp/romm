<script setup>
import storeDownload from "@/stores/download";

const props = defineProps(["rom"]);
const downloadStore = storeDownload();
</script>
<template>
  <v-row
    v-if="!rom.multi"
    class="d-flex align-center text-body-1 mt-0 py-2"
    no-gutters
  >
    <v-col cols="2" xs="2" sm="2" md="2" lg="1" xl="1" class="font-weight-medium">
      <span>File</span>
    </v-col>
    <v-col class="text-body-1">
      <span>{{ rom.file_name }}</span>
    </v-col>
  </v-row>
  <v-row
    v-if="rom.multi"
    class="d-flex align-center text-body-1 mt-0 py-2"
    no-gutters
  >
    <v-col cols="2" xs="2" sm="2" md="2" lg="1" xl="1" class="font-weight-medium">
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
  <v-row class="d-flex align-center text-body-1 mt-0 py-2" no-gutters>
    <v-col cols="2" xs="2" sm="2" md="2" lg="1" xl="1" class="font-weight-medium">
      <span>Size</span>
    </v-col>
    <v-col>
      <span>{{ rom.file_size }} {{ rom.file_size_units }}</span>
    </v-col>
  </v-row>
  <v-row
    v-if="rom.igdb_id"
    class="d-flex align-center text-body-1 py-2"
    no-gutters
  >
    <v-col cols="2" xs="2" sm="2" md="2" lg="1" xl="1" class="font-weight-medium">
      <span>IGDB</span>
    </v-col>
    <v-col>
      <v-chip
        variant="outlined"
        class="text-romm-accent-1"
        :href="`https://www.igdb.com/games/${rom.slug}`"
        label
      >
        {{ rom.igdb_id }}
      </v-chip>
    </v-col>
  </v-row>
  <v-row
    v-if="rom.tags.length > 0"
    class="d-flex align-center text-body-1 mt-0 py-2"
    no-gutters
  >
    <v-col cols="2" xs="2" sm="2" md="2" lg="1" xl="1" class="font-weight-medium">
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
  <v-row class="d-flex py-3" no-gutters>
    <v-col class="font-weight-medium text-caption">
      <p>{{ rom.summary }}</p>
    </v-col>
  </v-row>
</template>
