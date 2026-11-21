import { defineStore } from "pinia";
import { availableLocales, matchPreferredLocale } from "@/locales";

// Display names for the locale folders under src/locales, in their own language.
export const LOCALE_NAMES: Record<string, string> = {
  en_US: "English (USA)",
  en_GB: "English (United Kingdom)",
  fr_FR: "Français",
  de_DE: "Deutsch",
  ru_RU: "Русский",
  pt_BR: "Português (Brasil)",
  ro_RO: "Română",
  es_ES: "Español (España)",
  sv_SE: "Svenska",
  zh_CN: "简体中文 (中国)",
  zh_TW: "繁體中文 (台灣)",
  ko_KR: "한국어 (대한민국)",
  ja_JP: "日本語 (日本)",
  it_IT: "Italiano",
  pl_PL: "Polski",
  cs_CZ: "Česky",
  hu_HU: "Magyar",
  bg_BG: "Български",
  tr_TR: "Türkçe",
};

function languageOf(value: string) {
  return { value, name: LOCALE_NAMES[value] ?? value };
}

const defaultLanguageState = {
  defaultLanguage: languageOf("en_US"),
  selectedLanguage: languageOf("en_US"),
  languages: availableLocales
    .map(languageOf)
    .sort((a, b) => a.name.localeCompare(b.name)),
};

export default defineStore("language", {
  state: () => ({ ...defaultLanguageState }),

  actions: {
    setLanguage(lang: { value: string; name: string }) {
      this.selectedLanguage = lang;
    },
    detectBrowserLanguage(preferred: readonly string[] = navigator.languages) {
      const match = matchPreferredLocale(
        preferred,
        this.languages.map((lang) => lang.value),
      );
      return (
        this.languages.find((lang) => lang.value === match) ??
        this.defaultLanguage
      );
    },
    reset() {
      Object.assign(this, { ...defaultLanguageState });
    },
  },
});
