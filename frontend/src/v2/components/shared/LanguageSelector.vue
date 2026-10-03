<script setup lang="ts">
// LanguageSelector: wraps the language store in an RSelect so it
// shares aesthetics with every other v2 select (status picker on the
// Overview tab, etc). Persists the choice via useUISettings, with "Auto"
// following the browser's language.
//
// Two looks:
//   • Default: compact pill, used on Auth/Pair shells.
//   • `prefixLabel`: full-width prefix-label field, used in Settings.
import { RIcon, RSelect } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDetectedLanguage } from "@/composables/useBrowserLocale";
import { useUISettings } from "@/composables/useUISettings";
import storeLanguage from "@/stores/language";

defineOptions({ inheritAttrs: false });

interface Props {
  prefixLabel?: boolean;
}
withDefaults(defineProps<Props>(), { prefixLabel: false });

const { t } = useI18n();
const { languages } = storeToRefs(storeLanguage());
const { locale: storedLocale } = useUISettings();
const detectedLanguage = useDetectedLanguage();

// An empty stored locale means "Auto": useBrowserLocale (mounted at the app
// root) applies whatever is stored, so writing here is enough to switch.
const AUTO = "auto";

const items = computed(() => [
  {
    value: AUTO,
    title: t("settings.language-auto", {
      language: detectedLanguage.value.name,
    }),
  },
  ...languages.value.map((l) => ({ value: l.value, title: l.name })),
]);

const currentValue = computed({
  get: () =>
    languages.value.some((l) => l.value === storedLocale.value)
      ? storedLocale.value
      : AUTO,
  set: (next: string) => {
    storedLocale.value = next === AUTO ? "" : next;
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
