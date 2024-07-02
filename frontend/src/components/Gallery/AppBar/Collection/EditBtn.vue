<script setup lang="ts">
import storeRoms from "@/stores/roms";
import type { Collection } from "@/stores/collections";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useRoute } from "vue-router";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
const roms = storeRoms();
</script>

<template>
  <v-list-item
    v-if="route.params.collection"
    class="py-4 pr-5"
    @click="
      emitter?.emit(
        'showEditCollectionDialog',
        roms.currentCollection as Collection
      )
    "
  >
    <v-list-item-title class="d-flex">
      <v-icon icon="mdi-pencil-box" class="mr-2" />
      Edit collection
    </v-list-item-title>
  </v-list-item>
</template>
