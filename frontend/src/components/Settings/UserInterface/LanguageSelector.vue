<script setup lang="ts">
import languageStore from "@/stores/language";
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

const { locale } = useI18n();
const storeLanguage = languageStore();
const { languages, selectedLanguage } = storeToRefs(storeLanguage);

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
