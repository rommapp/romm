<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
defineProps<{
  set: string[];
  editable: boolean;
  title: string;
  emit: string;
  icon?: string;
}>();
</script>
<template>
  <v-card rounded="0" color="terciary">
    <v-card-title class="text-body-2 align-center justify-center"
      ><v-icon class="mr-2">{{ icon }}</v-icon
      >{{ title }}</v-card-title
    >
    <v-divider />
    <v-card-text class="pa-2">
      <v-chip v-for="excluded in set" :key="excluded" label class="ma-1">
        {{ excluded }}
      </v-chip>
      <v-expand-transition>
        <v-btn
          v-if="editable"
          rounded="1"
          prepend-icon="mdi-plus"
          variant="outlined"
          class="text-romm-accent-1 ml-1"
          @click="
            emitter?.emit('showCreateExclusionDialog', {
              exclude: emit,
            })
          "
        >
          Add
        </v-btn>
      </v-expand-transition>
    </v-card-text>
  </v-card>
</template>
