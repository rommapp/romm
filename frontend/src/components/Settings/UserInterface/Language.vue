<script setup lang="ts">
import { useI18n } from "vue-i18n";
import LanguageSelector from "@/components/Settings/UserInterface/LanguageSelector.vue";
import RSection from "@/components/common/RSection.vue";

const { t } = useI18n();
</script>
<template>
  <RSection icon="mdi-translate" :title="t('settings.language')" class="ma-2">
    <template #content>
      <LanguageSelector />
    </template>
  </RSection>
</template>
