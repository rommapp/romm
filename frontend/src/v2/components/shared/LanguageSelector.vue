<script setup lang="ts">
// LanguageSelector — wraps the language store in an RSelect so it
// shares aesthetics with every other v2 select (status picker on the
// Overview tab, etc). Persists the choice via useUISettings + sets the
// vue-i18n locale.
//
// Two looks:
//   • Default — compact pill, used on Auth/Pair shells.
//   • `prefixLabel` — full-width prefix-label field, used in Settings.
import { RIcon, RSelect } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useUISettings } from "@/composables/useUISettings";
import storeLanguage from "@/stores/language";

defineOptions({ inheritAttrs: false });

interface Props {
  prefixLabel?: boolean;
}
withDefaults(defineProps<Props>(), { prefixLabel: false });

const { t, locale } = useI18n();
const languageStore = storeLanguage();
const { languages, selectedLanguage } = storeToRefs(languageStore);
const { locale: localeStorage } = useUISettings();

const items = computed(() =>
  languages.value.map((l) => ({ value: l.value, title: l.name })),
);

const currentValue = computed({
  get: () => selectedLanguage.value.value,
  set: (next: string) => {
    const lang = languages.value.find((l) => l.value === next);
    if (!lang) return;
    selectedLanguage.value = lang;
    locale.value = lang.value;
    localeStorage.value = lang.value;
  },
});
</script>

<template>
  <RSelect
    v-if="prefixLabel"
    v-model="currentValue"
    :items="items"
    prefix-label="stacked"
    hide-details
  >
    <template #prefix-label>
      <RIcon icon="mdi-translate" size="14" />
      {{ t("settings.language") }}
    </template>
  </RSelect>
  <RSelect
    v-else
    v-model="currentValue"
    :items="items"
    density="compact"
    variant="outlined"
    hide-details
    prepend-inner-icon="mdi-translate"
    class="language-selector"
    :menu-props="{ location: 'top start' }"
  />
</template>

<style scoped>
.language-selector {
  min-width: 200px;
  max-width: 240px;
}
</style>
