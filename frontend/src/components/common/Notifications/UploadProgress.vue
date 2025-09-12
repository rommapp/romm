<script setup lang="ts">
import { storeToRefs } from "pinia";
import { ref, watch } from "vue";
import { useDisplay } from "vuetify";
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";

const { xs } = useDisplay();
const uploadStore = storeUpload();
const { files } = storeToRefs(uploadStore);
const show = ref(false);

function clearFinished() {
  uploadStore.clearFinished();
}

watch(files, (newList) => {
  show.value = newList.length > 0;
});
</script>

<template>
  <v-snackbar
    id="upload-in-progress"
    v-model="show"
    transition="scroll-y-transition"
    :timeout="-1"
    absolute
    :location="xs ? 'bottom' : 'bottom right'"
    class="mb-4 mr-4"
    color="toplayer"
  >
    <v-list class="bg-toplayer pa-0">
      <v-list-item
        v-for="file in files"
        :key="file.filename"
        class="py-2 px-4 bg-toplayer"
        :disabled="file.finished && !file.failed"
      >
        <template v-if="file.failed">
          <v-list-item-title class="d-flex justify-space-between">
            {{ file.filename }}
            <v-icon :icon="`mdi-close`" :color="`red`" class="mx-2" />
          </v-list-item-title>
          <v-list-item-subtitle v-if="file.failureReason" class="text-red mt-1">
            {{ file.failureReason }}
          </v-list-item-subtitle>
        </template>
        <template v-else>
          <v-list-item-title class="d-flex justify-space-between">
            {{ file.filename }}
            <v-icon
              :icon="file.finished ? 'mdi-check' : 'mdi-loading mdi-spin'"
              :color="file.finished ? 'green' : 'primary'"
              class="mx-2"
            />
          </v-list-item-title>
          <template v-if="file.progress > 0 && !file.finished">
            <v-progress-linear
              v-model="file.progress"
              height="4"
              color="primary"
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
        </template>
      </v-list-item>
    </v-list>
    <div class="bg-surface text-center">
      <v-btn
        size="small"
        class="my-2"
        color="primary"
        variant="text"
        :disabled="!files.some((f) => f.finished || f.failed)"
        @click="clearFinished"
      >
        Clear finished
      </v-btn>
    </div>
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
