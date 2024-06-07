<script setup lang="ts">
import storeDownload from "@/stores/download";
import { type SimpleRom } from "@/stores/roms";

defineProps<{ rom: SimpleRom }>();
const downloadStore = storeDownload();
import { useTheme } from "vuetify";
const theme = useTheme();
</script>
<template>
  <v-card
    elevation="2"
    :loading="downloadStore.value.includes(rom.id) ? 'romm-accent-1' : false"
  >
    <v-img
      :key="rom.id"
      :value="rom.id"
      :src="
        !rom.igdb_id && !rom.moby_id
          ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
          : `/assets/romm/resources/${rom.path_cover_l}`
      "
      :aspect-ratio="3 / 4"
      lazy
    >
      <slot name="editable" />
      <template #error>
        <v-img
          :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
          :aspect-ratio="3 / 4"
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
