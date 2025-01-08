<script setup lang="ts">
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
</script>
<template>
  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    icon="mdi-upload"
    variant="flat"
    rounded="0"
    @click="emitter?.emit('showUploadRomDialog', null)"
  />
</template>
