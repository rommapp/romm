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
  ].sort((a, b) => a.name.localeCompare(b.name)),
};

export default defineStore("language", {
  state: () => ({ ...defaultLanguageState }),

  actions: {
    setLanguage(lang: { value: string; name: string }) {
      this.selectedLanguage = lang;
    },
    reset() {
      Object.assign(this, { ...defaultLanguageState });
    },
  },
});
