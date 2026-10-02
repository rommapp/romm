import { useLocalStorage, usePreferredLanguages } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";
import i18n, { loadLocale } from "@/locales";
import storeLanguage from "@/stores/language";

// Applies the stored language, or the browser's preferred one until a language
// is picked manually, following browser changes live.
export function useBrowserLocale() {
  const languageStore = storeLanguage();
  const { languages } = storeToRefs(languageStore);
  const storedLocale = useLocalStorage("settings.locale", "");
  const preferredLanguages = usePreferredLanguages();

  const language = computed(
    () =>
      languages.value.find((lang) => lang.value === storedLocale.value) ??
      languageStore.detectBrowserLanguage(preferredLanguages.value),
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
