<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
defineProps<{ rail: boolean }>();

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-list-item>
    <v-row no-gutters>
      <v-col class="pa-1" :cols="rail ? 12 : 6">
        <v-btn
          :icon="rail"
          color="terciary"
          rounded="xl"
          size="small"
          variant="flat"
          @click="emitter?.emit('showSearchRomDialog', null)"
          ><v-icon>mdi-magnify</v-icon><span v-if="!rail">Search</span></v-btn
        > </v-col
      ><v-col class="pa-1" :cols="rail ? 12 : 6">
        <v-btn
          :icon="rail"
          color="terciary"
          rounded="xl"
          variant="flat"
          size="small"
          @click="emitter?.emit('showUploadRomDialog', null)"
          ><v-icon>mdi-upload</v-icon><span v-if="!rail">Upload</span></v-btn
        >
      </v-col>
    </v-row>
  </v-list-item>
</template>
