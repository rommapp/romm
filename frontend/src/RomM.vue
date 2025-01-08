<script setup lang="ts">
import languageStore from "@/stores/language";
import MainAppBar from "@/components/common/Navigation/MainAppBar.vue";
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
    <div class="d-flex flex-row flex-grow-1" style="max-height: 100dvh">
      <main-app-bar />
      <div class="flex-grow-1 overflow-y-scroll">
        <router-view />
      </div>
    </div>
  </v-app>
</template>
