<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import type { Rom } from "@/stores/roms";
import storeHeartbeat from "@/stores/heartbeat";

defineProps<{ rom: Rom }>();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      :disabled="!heartbeat.value.ANY_SOURCE_ENABLED"
      :title="!heartbeat.value.ANY_SOURCE_ENABLED ? 'No metadata source enabled' : ''"
      @click="emitter?.emit('showMatchRomDialog', rom)"
      class="py-4 pr-5"
    >
      <v-list-item-title class="d-flex"
        ><v-icon icon="mdi-search-web" class="mr-2" />Manual search</v-list-item-title
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
