<script setup lang="ts">
import languageStore from "@/stores/language";
import { storeToRefs } from "pinia";
import { ref } from "vue";
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
</script>

<template>
  <v-app>
    <v-main id="main" class="no-transition">
      <router-view v-slot="{ Component }">
        <component :is="Component" />
        <Transition name="fade" mode="out-in">
          <div v-if="!Component" id="app-loading-logo">
            <img
              src="/assets/logos/romm_logo_xbox_one_circle_grayscale.svg"
              alt="Romm Logo"
            />
          </div>
        </Transition>
      </router-view>
    </v-main>
  </v-app>
</template>

<style scoped>
#main.no-transition {
  transition: none;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
