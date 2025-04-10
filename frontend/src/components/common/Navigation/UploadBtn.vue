<script setup lang="ts">
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
</script>
<template>
  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="bg-background custom-btn"
    @click="emitter?.emit('showUploadRomDialog', null)"
  >
    <div class="icon-container">
      <v-icon>mdi-cloud-upload-outline</v-icon>
      <v-expand-transition>
        <span v-if="withTag" class="text-caption">Upload</span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>

<style scoped>
.custom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.icon-container span {
  text-align: center;
}
</style>
