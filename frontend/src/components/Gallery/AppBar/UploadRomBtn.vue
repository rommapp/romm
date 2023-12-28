<script setup>
import { inject } from "vue";

// Props
const emitter = inject("emitter");
</script>

<template>
    <v-btn
      @click="emitter.emit('showUploadRomDialog')"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-upload"
    />
</template>