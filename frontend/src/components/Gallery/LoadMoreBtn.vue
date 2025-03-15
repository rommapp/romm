<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

defineProps<{
  fetchRoms: () => void;
}>();
const { t } = useI18n();
const romsStore = storeRoms();
const { allRoms, fetchingRoms, fetchTotalRoms } = storeToRefs(romsStore);
</script>

<template>
  <v-row class="mx-1 py-3 justify-center" no-gutters>
    <v-col cols="2" class="text-center">
      <template v-if="fetchTotalRoms > allRoms.length">
        <v-btn
          @click="fetchRoms"
          :loading="fetchingRoms"
          :disabled="fetchingRoms"
          size="large"
          variant="flat"
        >
          {{ t("gallery.load-more") }}
        </v-btn>
      </template>
      <template v-else>
        <v-alert
          dense
          outlined
          color="surface"
          class="mx-auto text-gray px-6 py-4"
          max-width="fit-content"
        >
          {{ t("gallery.all-loaded") }}
        </v-alert>
      </template>
    </v-col>
  </v-row>
</template>
