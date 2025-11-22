<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <v-empty-state
    headline="Whoops, 404"
    :title="t('emptyStates.firmware-title')"
    :text="t('emptyStates.firmware-text')"
    icon="mdi-memory"
  />
</template>
