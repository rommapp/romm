import { usePreferredLanguages } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";
import i18n, { loadLocale } from "@/locales";
import storeLanguage from "@/stores/language";

// The available language that best matches the browser's preferences.
export function useDetectedLanguage() {
  const languageStore = storeLanguage();
  const preferredLanguages = usePreferredLanguages();
  return computed(() =>
    languageStore.detectBrowserLanguage(preferredLanguages.value),
  );
}

// Applies the stored language, or the browser's preferred one while none is
// stored ("Auto"), following browser changes live.
export function useBrowserLocale() {
  const languageStore = storeLanguage();
  const { languages } = storeToRefs(languageStore);
  const storedLocale = useUserLocalStorage("settings.locale", "");
  const detectedLanguage = useDetectedLanguage();

  const language = computed(
    () =>
      languages.value.find((lang) => lang.value === storedLocale.value) ??
      detectedLanguage.value,
  );

  watch(
    language,
    async (lang) => {
      // Switching before the messages land would flash the fallback language.
      await loadLocale(lang.value);
      if (language.value !== lang) return;
      i18n.global.locale.value = lang.value;
      languageStore.setLanguage(lang);
    },
    { immediate: true },
  );

  return language;
}
