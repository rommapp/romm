<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import languageStore from "@/stores/language";
import { storeToRefs } from "pinia";

// Props
const { locale } = useI18n();
const storeLanguage = languageStore();
const { languages, selectedLanguage } = storeToRefs(storeLanguage);

// Functions
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
