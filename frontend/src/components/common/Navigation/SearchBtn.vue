<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

const emitter = inject<Emitter<Events>>("emitter");
</script>
<template>
  <v-btn
    icon="mdi-magnify"
    size="small"
    variant="flat"
    @click="emitter?.emit('showSearchRomDialog', null)"
  />
</template>
