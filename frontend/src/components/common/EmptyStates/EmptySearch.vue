<script lang="ts" setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <v-empty-state :title="t('emptyStates.search-for-games')">
    <template #media>
      <v-icon size="70">mdi-magnify</v-icon>
    </template>
  </v-empty-state>
</template>
