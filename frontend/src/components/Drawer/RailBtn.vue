<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
defineProps<{ rail?: boolean }>();

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-btn
    rounded="0"
    :icon="rail ? 'mdi-arrow-collapse-right' : 'mdi-arrow-collapse-left'"
    size="small"
    variant="text"
    block
    @click="emitter?.emit('toggleDrawerRail', null)"
  />
</template>
