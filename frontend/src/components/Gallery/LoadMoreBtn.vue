<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

defineProps<{
  fetchRoms: () => void;
}>();
const { t } = useI18n();
const romsStore = storeRoms();
const { fetchingRoms, fetchTotalRoms, fetchLimit, fetchOffset } =
  storeToRefs(romsStore);
</script>

<template>
  <v-row
    v-if="fetchTotalRoms > fetchLimit"
    class="mx-1 py-3 justify-center"
    no-gutters
  >
    <v-col cols="2" class="text-center">
      <template v-if="fetchTotalRoms > fetchOffset">
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
        <v-alert dense outlined color="surface" class="mx-auto text-gray pa-4">
          {{ t("gallery.all-loaded") }}
        </v-alert>
      </template>
    </v-col>
  </v-row>
</template>
