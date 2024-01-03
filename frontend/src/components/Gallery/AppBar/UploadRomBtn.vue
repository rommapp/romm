<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

// Props
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
    <v-btn
      @click="emitter?.emit('showUploadRomDialog', null)"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-upload"
    />
</template>
