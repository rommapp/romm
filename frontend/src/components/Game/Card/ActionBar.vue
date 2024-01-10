<script setup lang="ts">
import { ref } from "vue";
import api from "@/services/api";
import storeDownload from "@/stores/download";
import storeAuth from "@/stores/auth";
import AdminMenu from "@/components/Game/AdminMenu/Base.vue";
import type { Rom } from "@/stores/roms";

// Props
defineProps<{ rom: Rom }>();
const auth = storeAuth();
const downloadStore = storeDownload();
</script>

<template>
  <v-card-text>
    <v-row>
      <v-col class="pa-0">
        <v-btn
          class="action-bar-btn"
          @click="api.downloadRom({ rom })"
          :disabled="downloadStore.value.includes(rom.id)"
          icon="mdi-download"
          size="x-small"
          rounded="0"
          variant="text"
        />
        <!-- <v-btn
        class="action-bar-btn"
          icon="mdi-play"
          size="x-small"
          rounded="0"
          variant="text"
          disabled
        /> -->
      </v-col>
      <v-menu location="bottom">
        <template v-slot:activator="{ props }">
          <v-btn
            class="action-bar-btn"
            :disabled="!auth.scopes.includes('roms.write')"
            v-bind="props"
            icon="mdi-dots-vertical"
            size="x-small"
            rounded="0"
            variant="text"
          />
        </template>
        <admin-menu :rom="rom" />
      </v-menu>
    </v-row>
  </v-card-text>
</template>

<style scoped>
.action-bar-btn {
  max-width: 27px;
  max-height: 27px;
}
</style>
