<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
import ThemeOption from "@/components/Settings/UserInterface/ThemeOption.vue";
import RSection from "@/components/common/RSection.vue";
import { autoThemeKey, themes } from "@/styles/themes";
import { isKeyof } from "@/types";

const { t } = useI18n();
const theme = useTheme();
const selectedTheme = useLocalStorage("settings.theme", autoThemeKey);
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

function toggleTheme() {
  const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
  if (selectedTheme.value === autoThemeKey) {
    theme.global.name.value = mediaMatch.matches ? "dark" : "light";
  } else if (isKeyof(selectedTheme.value, themes)) {
    theme.global.name.value = themes[selectedTheme.value];
  }
}
</script>
<template>
  <RSection icon="mdi-brush-variant" :title="t('settings.theme')" class="ma-2">
    <template #content>
      <v-item-group
        v-model="selectedTheme"
        mandatory
        @update:model-value="toggleTheme"
      >
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
