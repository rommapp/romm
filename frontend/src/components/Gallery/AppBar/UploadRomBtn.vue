<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

// Props
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-list-item
    @click="emitter?.emit('showUploadRomDialog', null)"
    class="py-4 pr-5"
  >
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-upload" class="mr-2" />Upload game</v-list-item-title
    >
  </v-list-item>
</template>
