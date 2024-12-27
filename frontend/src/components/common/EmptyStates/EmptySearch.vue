<script lang="ts" setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <v-empty-state>
    <template #media>
      <v-icon size="80">mdi-magnify</v-icon>
    </template>
    <template #title>
      <div class="text-h5 font-weight-medium text-medium-emphasis">
        {{ t("emptyStates.search-for-games") }}
      </div>
    </template>
  </v-empty-state>
</template>
