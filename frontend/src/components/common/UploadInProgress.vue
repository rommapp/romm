<script setup lang="ts">
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";
import { ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

const { xs } = useDisplay();
const uploadStore = storeUpload();
const { filenames, progress, total, loaded, rate, finished } =
  storeToRefs(uploadStore);
const show = ref(false);

watch(filenames, (fns) => {
  show.value = fns.length > 0;
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
        <v-list-item-title  class="py-2 px-4 d-flex justify-space-between">
          Uploading {{ filenames.length }} files...
          <v-icon icon="mdi-loading mdi-spin" color="white" class="mx-2"/>
        </v-list-item-title>
      <v-list-item class="py-1 px-4">
        <v-list-item-title v-for="filename in filenames" class="d-flex justify-space-between">
          <div class="upload-speeds">
            • {{ filename }}
          </div>
        </v-list-item-title>
      </v-list-item>
      <v-list-item class="py-0 px-4">
        <template v-if="progress > 0 && !finished">
          <v-progress-linear
            v-model="progress"
            height="4"
            color="white"
            class="mt-1"
          />
          <div class="upload-speeds d-flex justify-space-between mt-1">
            <div>{{ formatBytes(rate) }}/s</div>
            <div>
              {{ formatBytes(loaded) }} /
              {{ formatBytes(total) }}
            </div>
          </div>
        </template>
        <template v-if="finished">
          <div class="upload-speeds d-flex justify-space-between mt-1">
            <div />
            <div>
              {{ formatBytes(total) }}
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
  font-size: 12px;
}
</style>
