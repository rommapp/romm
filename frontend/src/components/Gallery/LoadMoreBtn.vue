<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import storeRoms from "@/stores/roms";

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
    class="justify-center my-2"
    no-gutters
  >
    <v-col cols="6" md="4" lg="2" class="text-center">
      <template v-if="fetchTotalRoms > fetchOffset">
        <v-btn
          :loading="fetchingRoms"
          :disabled="fetchingRoms"
          variant="flat"
          @click="fetchRoms"
        >
          <template #loader>
            <v-progress-circular
              color="primary"
              :width="2"
              :size="20"
              indeterminate
            />
          </template>
          {{ t("gallery.load-more") }}
        </v-btn>
      </template>
      <template v-else>
        <v-alert dense outlined color="surface" class="text-caption pa-2">
          {{ t("gallery.all-loaded") }}
        </v-alert>
      </template>
    </v-col>
  </v-row>
</template>
