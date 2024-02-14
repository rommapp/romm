<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      @click="emitter?.emit('showSearchRomDialog', rom)"
      class="py-4 pr-5"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-search-web" class="mr-2" />Search…</v-list-item-title
      >
    </v-list-item>
    <v-divider class="border-opacity-25" />
    <v-list-item
      @click="emitter?.emit('showEditRomDialog', { ...rom })"
      class="py-4 pr-5"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-pencil-box" class="mr-2" />Edit</v-list-item-title
      >
    </v-list-item>
    <v-divider class="border-opacity-25" />
    <v-list-item
      @click="emitter?.emit('showDeleteRomDialog', [rom])"
      class="py-4 pr-5 text-romm-red"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-delete" class="mr-2" />Delete</v-list-item-title
      >
    </v-list-item>
  </v-list>
</template>
