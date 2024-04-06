<script setup lang="ts">
import storeDownload from "@/stores/download";

defineProps<{ romId: number; src: string; lazySrc: string }>();
const downloadStore = storeDownload();
</script>
<template>
  <v-card
    elevation="2"
    :loading="downloadStore.value.includes(romId) ? 'romm-accent-1' : false"
  >
    <v-img
      :value="romId"
      :key="romId"
      :src="src"
      :lazy-src="lazySrc"
      :aspect-ratio="3 / 4"
    >
      <slot name="editable"></slot>
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
</template>
