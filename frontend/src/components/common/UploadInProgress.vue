<script setup lang="ts">
import storeUpload from "@/stores/upload";
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
        <v-list-item-title class="d-flex">
          <v-icon
            :icon="rom.finished ? `mdi-check` : `mdi-loading mdi-spin`"
            :color="rom.finished ? `green` : `white`"
            class="mx-2"
          />
          {{ rom.filename }}...
        </v-list-item-title>
        <v-progress-linear
          v-if="!rom.finished"
          v-model="rom.progress"
          height="4"
          color="white"
          class="mt-2"
        />
      </v-list-item>
    </v-list>
  </v-snackbar>
</template>

<style>
#upload-in-progress .v-snackbar__content {
  padding: 0;
}
</style>
