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
    class="py-4 pr-5 text-romm-red"
    @click="
      emitter?.emit(
        'showDeletePlatformDialog',
        platforms.get(Number(route.params.platform)) as Platform
      )
    "
  >
    <v-list-item-title class="d-flex">
      <v-icon icon="mdi-delete" color="red" class="mr-2" />
      Delete platform
    </v-list-item-title>
  </v-list-item>
</template>
