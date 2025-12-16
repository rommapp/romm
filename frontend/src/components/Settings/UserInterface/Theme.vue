<script setup lang="ts">
import { computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
import ThemeOption from "@/components/Settings/UserInterface/ThemeOption.vue";
import RSection from "@/components/common/RSection.vue";
import { useUISettings } from "@/composables/useUISettings";
import { autoThemeKey, themes } from "@/styles/themes";
import { isKeyof } from "@/types";

const { t } = useI18n();
const theme = useTheme();
const { theme: selectedTheme } = useUISettings();
const themeOptions = computed(() => [
  {
    name: "dark",
    icon: "mdi-moon-waning-crescent",
  },
  {
    name: "light",
    icon: "mdi-white-balance-sunny",
  },
  {
    name: "auto",
    icon: "mdi-theme-light-dark",
  },
]);

function applyTheme() {
  const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
  if (selectedTheme.value === autoThemeKey) {
    theme.change(mediaMatch.matches ? "dark" : "light");
  } else if (isKeyof(selectedTheme.value, themes)) {
    theme.change(themes[selectedTheme.value]);
  }
}

// Apply theme when it changes (including from backend sync)
watch(selectedTheme, applyTheme, { immediate: true });
</script>
<template>
  <RSection icon="mdi-brush-variant" :title="t('settings.theme')" class="ma-2">
    <template #content>
      <v-item-group v-model="selectedTheme" mandatory>
        <v-row no-gutters>
          <v-col
            v-for="themeOption in themeOptions"
            :key="themeOption.name"
            cols="4"
            sm="3"
            md="2"
            class="pa-2"
          >
            <ThemeOption
              :key="themeOption.name"
              :text="themeOption.name"
              :icon="themeOption.icon"
            />
          </v-col>
        </v-row>
      </v-item-group>
    </template>
  </RSection>
</template>
