<script setup lang="ts">
import { type Platform } from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useRoute } from "vue-router";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const roms = storeRoms();
const route = useRoute();
</script>

<template>
  <v-list-item
    v-if="route.params.platform"
    class="py-4 pr-5 text-romm-red"
    @click="
      emitter?.emit(
        'showDeletePlatformDialog',
        roms.currentPlatform as Platform
      )
    "
  >
    <v-list-item-title class="d-flex">
      <v-icon icon="mdi-delete" color="red" class="mr-2" />
      Delete platform
    </v-list-item-title>
  </v-list-item>
</template>
