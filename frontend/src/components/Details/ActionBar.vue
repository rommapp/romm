<script setup lang="ts">
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import api from "@/services/api";
import storeDownload from "@/stores/download";
import AdminMenu from "@/components/AdminMenu/Base.vue";

const props = defineProps(["rom"]);
const downloadStore = storeDownload();
const auth = storeAuth();
const saveFiles = ref(false);
</script>

<template>
  <v-row class="my-3" no-gutters>
    <v-col class="pa-0">
      <v-btn
        @click="
          api.downloadRom({
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
    <v-col class="pa-0">
      <v-btn rounded="0" block :disabled="!saveFiles"
        ><v-icon icon="mdi-content-save-all" size="large"
      /></v-btn>
    </v-col>
    <v-col class="pa-0">
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
