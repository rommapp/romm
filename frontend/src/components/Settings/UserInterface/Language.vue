<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import LanguageSelector from "@/components/Settings/UserInterface/LanguageSelector.vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
</script>
<template>
  <r-section icon="mdi-translate" :title="t('settings.language')">
    <template #content>
      <language-selector />
    </template>
  </r-section>
</template>
