<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <v-row class="text-center">
    <v-col>
      <v-icon size="large">mdi-help-rhombus-outline</v-icon>
      <p class="text-h6 mt-2">{{ t("rom.no-states-found") }}</p>
    </v-col>
  </v-row>
</template>
