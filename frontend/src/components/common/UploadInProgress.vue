<script setup lang="ts">
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";
import { ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

const { xs } = useDisplay();
const uploadStore = storeUpload();
const { value: romsList } = storeToRefs(uploadStore);
const show = ref(false);

watch(romsList, (newList) => {
  show.value = newList.length > 0;
});
</script>

<template>
  <v-snackbar
    id="upload-in-progress"
    v-model="show"
    transition="scroll-y-transition"
    :timeout="100000000000"
    absolute
    :location="xs ? 'bottom' : 'bottom right'"
    class="mb-4 mr-4"
    color="tooltip"
  >
    <v-list>
      <v-list-item
        v-for="rom in romsList"
        class="py-2 px-4"
        :disabled="rom.finished"
      >
        <v-list-item-title class="d-flex justify-space-between">
          {{ rom.filename }}
          <v-icon
            :icon="rom.finished ? `mdi-check` : `mdi-loading mdi-spin`"
            :color="rom.finished ? `green` : `white`"
            class="mx-2"
          />
        </v-list-item-title>
        <template v-if="rom.progress > 0 && !rom.finished">
          <v-progress-linear
            v-model="rom.progress"
            height="4"
            color="white"
            class="mt-1"
          />
          <div class="upload-speeds d-flex justify-space-between mt-1">
            <div>{{ formatBytes(rom.upload_speed) }}/s</div>
            <div>
              {{ formatBytes(rom.uploaded_size) }} /
              {{ formatBytes(rom.file_size) }}
            </div>
          </div>
        </template>
      </v-list-item>
    </v-list>
  </v-snackbar>
</template>

<style>
#upload-in-progress .v-snackbar__content {
  padding: 0;
}

.upload-speeds {
  font-size: 10px;
}
</style>
