<script setup lang="ts">
import { inject } from "vue";
import { useRoute } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storePlatforms, { type Platform } from "@/stores/platforms";

// Props
const platforms = storePlatforms();
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
const platform = platforms.value.find(
  (p: Platform) => p.slug === (route.params.platform as string)
);
</script>

<template>
  <v-list-item
    class="py-4 pr-5 text-red"
    @click="emitter?.emit('showDeletePlatformDialog', platform)"
  >
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-delete" color="red" class="mr-2" />Delete
      platform</v-list-item-title
    >
  </v-list-item>
</template>
