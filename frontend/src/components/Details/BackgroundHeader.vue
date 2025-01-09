<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useTheme } from "vuetify";

// Props
const theme = useTheme();
const romsStore = storeRoms();
const { currentRom } = storeToRefs(romsStore);
</script>

<template>
  <v-card id="background-header" :key="currentRom.updated_at" v-if="currentRom">
    <v-img
      id="background-image"
      :src="
        !currentRom.igdb_id && !currentRom.moby_id && !currentRom.has_cover
          ? `/assets/default/cover/${theme.global.name.value}_unmatched.svg`
          : `/assets/romm/resources/${currentRom.path_cover_l}?ts=${currentRom.updated_at}`
      "
      lazy
      cover
    >
      <template #error>
        <v-img
          :src="`/assets/default/cover/${theme.global.name.value}_missing_cover.svg`"
        />
      </template>
      <template #placeholder>
        <div class="d-flex align-center justify-center fill-height">
          <v-progress-circular
            :width="2"
            :size="40"
            color="primary"
            indeterminate
          />
        </div>
      </template>
    </v-img>
  </v-card>
</template>
<style scoped>
#background-header {
  width: 100%;
}

#background-image {
  height: 18rem;
  filter: blur(30px);
}
</style>
