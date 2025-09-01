<script setup lang="ts">
import languageStore from "@/stores/language";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useI18n } from "vue-i18n";

const { locale } = useI18n();
const storeLanguage = languageStore();
const { languages, selectedLanguage } = storeToRefs(storeLanguage);

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
