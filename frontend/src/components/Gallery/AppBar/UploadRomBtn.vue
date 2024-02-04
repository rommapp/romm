<script setup lang="ts">
import { inject } from "vue";
import { useRoute } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storePlatforms from "@/stores/platforms";

// Props
const platformsStore = storePlatforms();
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
const platform = platformsStore.get(Number(route.params.platform));
</script>

<template>
  <v-list-item
  v-if="platform"
    @click="emitter?.emit('showUploadRomDialog', platform)"
    class="py-4 pr-5"
  >
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-upload" class="mr-2" />Upload game</v-list-item-title
    >
  </v-list-item>
</template>
