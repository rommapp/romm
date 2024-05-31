<script setup lang="ts">
import { inject } from "vue";
import { useRoute } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storePlatforms, { type Platform } from "@/stores/platforms";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const platforms = storePlatforms();
const route = useRoute();
</script>

<template>
  <v-list-item
    v-if="route.params.platform"
    @click="
      emitter?.emit(
        'showFirmwareDialog',
        platforms.get(Number(route.params.platform)) as Platform
      )
    "
    class="py-4 pr-5"
  >
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-memory" class="mr-2" />Firmware/BIOS</v-list-item-title
    >
  </v-list-item>
</template>
