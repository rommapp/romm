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
    v-model="show"
    transition="scroll-y-transition"
    :timeout="100000000000"
    absolute
    :location="xs ? 'bottom' : 'bottom right'"
    color="tooltip"
  >
    <template v-for="rom in romsList">
      <v-icon icon="mdi-upload" color="white" class="mx-2" />
      Uploading {{ rom.filename }}
      <v-progress-linear
        v-model="rom.progress"
        height="2"
        color="romm-accent-1"
      />
    </template>
  </v-snackbar>
</template>
