<script setup>
import storeDownload from "@/stores/download";

const downloadStore = storeDownload();
const props = defineProps(["rom"]);
</script>
<template>
  <v-row no-gutters>
    <v-col>
      <v-card
        elevation="2"
        :loading="downloadStore.value.includes(rom.id) ? 'romm-accent-1' : null"
      >
        <v-img
          :src="`/assets/romm/resources/${rom.path_cover_l}`"
          :lazy-src="`/assets/romm/resources/${rom.path_cover_s}`"
          :aspect-ratio="3 / 4"
        >
          <template v-slot:placeholder>
            <div class="d-flex align-center justify-center fill-height">
              <v-progress-circular
                color="romm-accent-1"
                :width="2"
                :size="20"
                indeterminate
              />
            </div>
          </template>
        </v-img>
      </v-card>
    </v-col>
  </v-row>
</template>
