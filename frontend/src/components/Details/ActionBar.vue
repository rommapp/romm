<script setup lang="ts">
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import api_rom from "@/services/api_rom";
import storeDownload from "@/stores/download";
import AdminMenu from "@/components/Game/AdminMenu/Base.vue";
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
const downloadStore = storeDownload();
const auth = storeAuth();
const saveFiles = ref(false);
</script>

<template>
  <v-row no-gutters>
    <v-col>
      <v-btn
        @click="
          api_rom.downloadRom({
            rom,
            files: downloadStore.filesToDownloadMultiFileRom,
          })
        "
        :disabled="downloadStore.value.includes(rom.id)"
        rounded="0"
        color="primary"
        block
      >
        <v-icon icon="mdi-download" size="large" />
      </v-btn>
    </v-col>
    <v-col>
      <v-btn rounded="0" block disabled
        ><v-icon icon="mdi-play" size="large"
      /></v-btn>
    </v-col>
    <v-col>
      <v-menu location="bottom">
        <template v-slot:activator="{ props }">
          <v-btn
            :disabled="!auth.scopes.includes('roms.write')"
            v-bind="props"
            rounded="0"
            block
          >
            <v-icon icon="mdi-dots-vertical" size="large" />
          </v-btn>
        </template>
        <admin-menu :rom="rom" />
      </v-menu>
    </v-col>
  </v-row>
</template>
