<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import type { SimpleRom } from "@/stores/roms";
import storeHeartbeat from "@/stores/heartbeat";

defineProps<{ rom: SimpleRom }>();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      :disabled="!heartbeat.value.ANY_SOURCE_ENABLED"
      class="py-4 pr-5"
      @click="emitter?.emit('showMatchRomDialog', rom)"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-search-web" class="mr-2" />Manual match
      </v-list-item-title>
      <v-list-item-subtitle>
        {{
          !heartbeat.value.ANY_SOURCE_ENABLED
            ? "No metadata source enabled"
            : ""
        }}
      </v-list-item-subtitle>
    </v-list-item>

    <v-list-item
      :disabled="!heartbeat.value.STEAMGRIDDB_ENABLED"
      class="py-4 pr-5"
      @click="emitter?.emit('showSearchCoverDialog', rom)"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-image-outline" class="mr-2" />Cover search
      </v-list-item-title>
      <v-list-item-subtitle>
        {{
          !heartbeat.value.STEAMGRIDDB_ENABLED
            ? "SteamgridDB is not enabled"
            : ""
        }}
      </v-list-item-subtitle>
    </v-list-item>
    <v-list-item
      class="py-4 pr-5"
      @click="emitter?.emit('showEditRomDialog', { ...rom })"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-pencil-box" class="mr-2" />Edit
      </v-list-item-title>
    </v-list-item>
    <v-divider />
    <v-list-item
      class="py-4 pr-5"
      @click="emitter?.emit('showAddToCollectionDialog', [{ ...rom }])"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-bookmark-plus-outline" class="mr-2" />Add to
        collection
      </v-list-item-title>
    </v-list-item>
    <v-divider />
    <v-list-item
      class="py-4 pr-5 text-romm-red"
      @click="emitter?.emit('showDeleteRomDialog', [rom])"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-delete" class="mr-2" />Delete
      </v-list-item-title>
    </v-list-item>
  </v-list>
</template>
