<script setup>
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import { downloadRomApi } from "@/services/api";
import storeDownload from "@/stores/download";
import AdminMenu from "@/components/AdminMenu/Base.vue";

const props = defineProps(["rom", "downloadUrl"]);
const downloadStore = storeDownload();
const auth = storeAuth();
const saveFiles = ref(false);
</script>

<template>
  <v-row class="my-3" no-gutters>
    <v-col class="pa-0">
      <template v-if="rom.multi">
        <v-btn
          @click="
            downloadRomApi(rom, downloadStore.filesToDownloadMultiFileRom)
          "
          :disabled="downloadStore.value.includes(rom.id)"
          rounded="0"
          color="primary"
          block
        >
          <v-icon icon="mdi-download" size="large" />
        </v-btn>
      </template>
      <template v-else>
        <v-btn :href="downloadUrl" download rounded="0" color="primary" block>
          <v-icon icon="mdi-download" size="large" />
        </v-btn>
      </template>
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
