<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>
<template>
  <v-empty-state
    headline="404"
    :title="t('emptyStates.404-title')"
    :text="t('emptyStates.404-subtitle')"
  />
</template>
