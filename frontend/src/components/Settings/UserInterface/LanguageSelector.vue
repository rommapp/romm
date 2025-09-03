<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import storeLanguage from "@/stores/language";

const { locale } = useI18n();
const languageStore = storeLanguage();
const { languages, selectedLanguage } = storeToRefs(languageStore);

const localeStorage = useLocalStorage("settings.locale", "");

function changeLanguage() {
  locale.value = selectedLanguage.value.value;
  localeStorage.value = selectedLanguage.value.value;
}
</script>
<template>
  <v-autocomplete
    v-model="selectedLanguage"
    :items="languages"
    variant="outlined"
    class="ma-2"
    item-value="value"
    item-title="name"
    return-object
    hide-details
    clearable
    @update:model-value="changeLanguage"
  />
</template>
