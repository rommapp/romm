<script lang="ts" setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <v-empty-state :title="t('emptyStates.manual-match')">
    <template #media>
      <v-icon size="70">mdi-search-web</v-icon>
    </template>
  </v-empty-state>
</template>
