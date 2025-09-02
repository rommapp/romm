<script setup lang="ts">
import { useI18n } from "vue-i18n";
import storeLanguage from "@/stores/language";
import { storeToRefs } from "pinia";

const { locale } = useI18n();
const languageStore = storeLanguage();
const { languages, selectedLanguage } = storeToRefs(languageStore);

function changeLanguage() {
  locale.value = selectedLanguage.value.value;
  localStorage.setItem("settings.locale", selectedLanguage.value.value);
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
