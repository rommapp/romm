<script setup lang="ts">
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

defineProps<{ rom: SimpleRom }>();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const auth = storeAuth();
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <template v-if="auth.scopes.includes('roms.write')">
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
        class="py-4 pr-5"
        @click="emitter?.emit('showEditRomDialog', { ...rom })"
      >
        <v-list-item-title class="d-flex">
          <v-icon icon="mdi-pencil-box" class="mr-2" />Edit
        </v-list-item-title>
      </v-list-item>
      <v-divider />
    </template>
    <v-list-item
      v-if="auth.scopes.includes('collections.write')"
      class="py-4 pr-5"
      @click="emitter?.emit('showAddToCollectionDialog', [{ ...rom }])"
    >
      <v-list-item-title class="d-flex">
        <v-icon icon="mdi-bookmark-plus-outline" class="mr-2" />Add to
        collection
      </v-list-item-title>
    </v-list-item>
    <template v-if="auth.scopes.includes('roms.write')">
      <v-divider />
      <v-list-item
        class="py-4 pr-5 text-romm-red"
        @click="emitter?.emit('showDeleteRomDialog', [rom])"
      >
        <v-list-item-title class="d-flex">
          <v-icon icon="mdi-delete" class="mr-2" />Delete
        </v-list-item-title>
      </v-list-item>
    </template>
  </v-list>
</template>
