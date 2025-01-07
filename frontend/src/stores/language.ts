import { defineStore } from "pinia";

export default defineStore("language", {
  state: () => ({
    defaultLanguage: { value: "en_US", name: "English (USA)" },
    selectedLanguage: { value: "en_US", name: "English (USA)" },
    languages: [
      { value: "en_US", name: "English (USA)" },
      { value: "en_GB", name: "English (United Kingdom)" },
      { value: "fr_FR", name: "Français" },
      { value: "ru_RU", name: "Русский" },
      { value: "pt_BR", name: "Português (Brasil)" },
      { value: "es_ES", name: "Español (España)" },
      { value: "zh_CN", name: "简体中文 (中国)" },
      { value: "ko_KR", name: "한국어 (대한민국)" },
    ].sort((a, b) => a.name.localeCompare(b.name)),
  }),

  actions: {
    setLanguage(lang: { value: string; name: string }) {
      this.selectedLanguage = lang;
    },
  },
});
