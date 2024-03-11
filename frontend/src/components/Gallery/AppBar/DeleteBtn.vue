<script setup lang="ts">
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();
</script>

<template>
  <v-list-item
    v-if="romsStore.platform"
    class="py-4 pr-5 text-romm-red"
    @click="emitter?.emit('showDeletePlatformDialog', romsStore.platform)"
  >
    <v-list-item-title class="d-flex">
      <v-icon icon="mdi-delete" color="red" class="mr-2" />
      Delete platform
    </v-list-item-title>
  </v-list-item>
</template>
