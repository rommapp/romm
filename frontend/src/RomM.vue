<script setup lang="ts">
import languageStore from "@/stores/language";
import { storeToRefs } from "pinia";
import { nextTick, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

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

onMounted(() => {
  setTimeout(() => {
    const main = document.getElementById("main");
    if (main) main.style.transition = "0.2s cubic-bezier(0.4, 0, 0.2, 1)";
  }, 500);
});
</script>

<template>
  <v-app>
    <v-main id="main">
      <router-view />
    </v-main>
  </v-app>
</template>

<style scoped>
#main {
  transition: none;
}
</style>
