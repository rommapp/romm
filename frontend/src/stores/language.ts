import { defineStore } from "pinia";

export default defineStore("language", {
  state: () => ({
    defaultLanguage: { value: "en_US", name: "English (USA)" },
    selectedLanguage: { value: "en_US", name: "English (USA)" },
    languages: [
      { value: "en_US", name: "English (USA)" },
      { value: "en_GB", name: "English (United Kingdom)" },
      { value: "es_ES", name: "Español (España)" },
      { value: "fr_FR", name: "Français" },
      { value: "ru_RU", name: "Русский" },
    ],
  }),

  actions: {
    setLanguage(lang: { value: string; name: string }) {
      this.selectedLanguage = lang;
    },
  },
});
