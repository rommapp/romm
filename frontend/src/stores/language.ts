import { defineStore } from "pinia";

const defaultLanguageState = {
  defaultLanguage: { value: "en_US", name: "English (USA)" },
  selectedLanguage: { value: "en_US", name: "English (USA)" },
  languages: [
    { value: "en_US", name: "English (USA)" },
    { value: "en_GB", name: "English (United Kingdom)" },
    { value: "fr_FR", name: "Français" },
    { value: "de_DE", name: "Deutsch" },
    { value: "ru_RU", name: "Русский" },
    { value: "pt_BR", name: "Português (Brasil)" },
    { value: "ro_RO", name: "Română" },
    { value: "es_ES", name: "Español (España)" },
    { value: "zh_CN", name: "简体中文 (中国)" },
    { value: "zh_TW", name: "繁體中文 (台灣)" },
    { value: "ko_KR", name: "한국어 (대한민국)" },
    { value: "ja_JP", name: "日本語 (日本)" },
    { value: "it_IT", name: "Italiano" },
    { value: "pl_PL", name: "Polski" },
    { value: "cs_CZ", name: "Česky" },
    { value: "hu_HU", name: "Magyar" },
    { value: "bg_BG", name: "Български" },
    { value: "tr_TR", name: "Türkçe" },
  ].sort((a, b) => a.name.localeCompare(b.name)),
};

export default defineStore("language", {
  state: () => ({ ...defaultLanguageState }),

  actions: {
    setLanguage(lang: { value: string; name: string }) {
      this.selectedLanguage = lang;
    },
    // Match the browser's preferred languages against the available locales,
    // falling back to the default (en_US) when none line up. Tries an exact
    // match first (e.g. "en-US" -> "en_US"), then a language-only match
    // (e.g. "fr" -> "fr_FR").
    detectBrowserLanguage() {
      for (const pref of navigator.languages) {
        const normalized = pref.replace("-", "_").toLowerCase();
        const exact = this.languages.find(
          (lang) => lang.value.toLowerCase() === normalized,
        );
        if (exact) return exact;
        const base = normalized.split("_")[0];
        const partial = this.languages.find(
          (lang) => lang.value.toLowerCase().split("_")[0] === base,
        );
        if (partial) return partial;
      }
      return this.defaultLanguage;
    },
    reset() {
      Object.assign(this, { ...defaultLanguageState });
    },
  },
});
