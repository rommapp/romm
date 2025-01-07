<script setup lang="ts">
import languageStore from "@/stores/language";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { locale } = useI18n();
const storeLanguage = languageStore();
const { defaultLanguage, languages } = storeToRefs(storeLanguage);
const selectedLanguage = ref(
  languages.value.find(
    (lang) => lang.value === localStorage.getItem("settings.locale"),
  ) || defaultLanguage.value,
);
locale.value = selectedLanguage.value.value;
storeLanguage.setLanguage(selectedLanguage.value);
</script>
<template>
  <v-app>
    <v-main class="h-100">
      <router-view />
    </v-main>
  </v-app>
</template>
