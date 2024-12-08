<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import LanguageSelector from "@/components/Settings/UserInterface/LanguageSelector.vue";
</script>
<template>
  <r-section icon="mdi-translate" title="Language">
    <template #content>
      <language-selector />
    </template>
  </r-section>
</template>
