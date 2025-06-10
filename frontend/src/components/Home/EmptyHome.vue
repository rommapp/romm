<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <v-empty-state
    :headline="t('emptyStates.home-headline')"
    :title="t('emptyStates.home-title')"
    :text="t('emptyStates.home-text')"
  />
</template>
