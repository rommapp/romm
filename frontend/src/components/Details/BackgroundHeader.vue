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
  <v-card :key="currentRom.updated_at" v-if="currentRom" rounded="0">
    <v-img
      id="background-header"
      :src="
        !currentRom.igdb_id && !currentRom.moby_id && !currentRom.has_cover
          ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
          : `/assets/romm/resources/${currentRom.path_cover_l}?ts=${currentRom.updated_at}`
      "
      lazy
      cover
    >
      <template #error>
        <v-img
          :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
        />
      </template>
      <template #placeholder>
        <div class="d-flex align-center justify-center fill-height">
          <v-progress-circular
            :width="2"
            :size="40"
            color="romm-accent-1"
            indeterminate
          />
        </div>
      </template>
    </v-img>
  </v-card>
</template>
<style scoped>
#background-header {
  height: 300px;
  filter: blur(30px);
}
</style>
