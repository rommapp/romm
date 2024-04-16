<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storeRoms from "@/stores/roms";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();
</script>

<template>
  <v-list-item
  v-if="romsStore.platform"
    @click="emitter?.emit('showUploadRomDialog', romsStore.platform)"
    class="py-4 pr-5"
  >
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-upload" class="mr-2" />Upload roms</v-list-item-title
    >
  </v-list-item>
</template>
