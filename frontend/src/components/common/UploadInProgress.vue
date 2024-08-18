<script setup lang="ts">
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";
import { ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

const { xs } = useDisplay();
const uploadStore = storeUpload();
const { files } = storeToRefs(uploadStore);
const show = ref(false);

watch(files, (newList) => {
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
        v-for="file in files"
        class="py-2 px-4"
        :disabled="file.finished"
      >
        <v-list-item-title class="d-flex justify-space-between">
          {{ file.filename }}
          <v-icon
            :icon="file.finished ? `mdi-check` : `mdi-loading mdi-spin`"
            :color="file.finished ? `green` : `white`"
            class="mx-2"
          />
        </v-list-item-title>
        <template v-if="file.progress > 0 && !file.finished">
          <v-progress-linear
            v-model="file.progress"
            height="4"
            color="white"
            class="mt-1"
          />
          <div class="upload-speeds d-flex justify-space-between mt-1">
            <div>{{ formatBytes(file.rate) }}/s</div>
            <div>
              {{ formatBytes(file.loaded) }} /
              {{ formatBytes(file.total) }}
            </div>
          </div>
        </template>
        <template v-if="file.finished">
          <div class="upload-speeds d-flex justify-space-between mt-1">
            <div />
            <div>
              {{ formatBytes(file.total) }}
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
