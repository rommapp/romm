<script setup>
import { inject } from "vue";

const props = defineProps(["rom"]);
const emitter = inject("emitter");
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      @click="emitter.emit('showSearchRomDialog', rom)"
      class="py-4 pr-5"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-search-web" class="mr-2" />Search
        IGDB</v-list-item-title
      >
    </v-list-item>
    <v-divider class="border-opacity-25" />
    <v-list-item
      @click="emitter.emit('showEditRomDialog', { ...rom })"
      class="py-4 pr-5"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-pencil-box" class="mr-2" />Edit</v-list-item-title
      >
    </v-list-item>
    <v-divider class="border-opacity-25" />
    <v-list-item
      @click="emitter.emit('showDeleteRomDialog', [rom])"
      class="py-4 pr-5 text-red"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-delete" class="mr-2" />Delete</v-list-item-title
      >
    </v-list-item>
  </v-list>
</template>
