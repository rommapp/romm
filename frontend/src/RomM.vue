<script setup lang="ts">
import { useIdle, useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import storeConsole from "@/stores/console";
import storeLanguage from "@/stores/language";

const { locale } = useI18n();
const languageStore = storeLanguage();
const consoleStore = storeConsole();
const { consoleMode } = storeToRefs(consoleStore);
const { defaultLanguage, languages } = storeToRefs(languageStore);
const storedLocale = useLocalStorage("settings.locale", "");
const selectedLanguage = ref(
  languages.value.find((lang) => lang.value === storedLocale.value) ||
    defaultLanguage.value,
);
locale.value = selectedLanguage.value.value;
languageStore.setLanguage(selectedLanguage.value);

const { idle: mouseIdle } = useIdle(100, {
  events: ["mousemove", "mousedown", "wheel", "touchstart"],
});
</script>

<template>
  <v-app id="application" :class="{ 'mouse-hidden': consoleMode && mouseIdle }">
    <v-main id="main" class="no-transition">
      <router-view v-slot="{ Component }">
        <component :is="Component" />
        <!-- Fade out the app loading logo -->
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

#application.mouse-hidden,
#application.mouse-hidden * {
  cursor: none !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.35s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
