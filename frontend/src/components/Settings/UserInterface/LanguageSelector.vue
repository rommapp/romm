<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import storeLanguage from "@/stores/language";

const { locale } = useI18n();
const languageStore = storeLanguage();
const { languages, selectedLanguage } = storeToRefs(languageStore);
const localeStorage = useLocalStorage("settings.locale", "");

withDefaults(
  defineProps<{
    density: "comfortable" | "compact" | "default";
  }>(),
  {
    density: "default",
  },
);

function changeLanguage() {
  locale.value = selectedLanguage.value.value;
  localeStorage.value = selectedLanguage.value.value;
}
</script>
<template>
  <v-select
    v-model="selectedLanguage"
    :items="languages"
    variant="outlined"
    :density="density"
    item-value="value"
    item-title="name"
    return-object
    hide-details
    @update:model-value="changeLanguage"
  />
</template>
