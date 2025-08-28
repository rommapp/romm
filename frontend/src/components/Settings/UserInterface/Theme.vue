<script setup lang="ts">
import ThemeOption from "@/components/Settings/UserInterface/ThemeOption.vue";
import RSection from "@/components/common/RSection.vue";
import { autoThemeKey, themes } from "@/styles/themes";
import { isKeyof } from "@/types";
import { computed, ref } from "vue";
import { useTheme } from "vuetify";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const theme = useTheme();
const storedTheme = parseInt(localStorage.getItem("settings.theme") ?? "");
const selectedTheme = ref(isNaN(storedTheme) ? autoThemeKey : storedTheme);
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
  localStorage.setItem("settings.theme", selectedTheme.value.toString());
  const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
  if (selectedTheme.value === autoThemeKey) {
    theme.global.name.value = mediaMatch.matches ? "dark" : "light";
  } else if (isKeyof(selectedTheme.value, themes)) {
    theme.global.name.value = themes[selectedTheme.value];
  }
}
</script>
<template>
  <r-section icon="mdi-brush-variant" :title="t('settings.theme')" class="ma-2">
    <template #content>
      <v-item-group
        v-model="selectedTheme"
        mandatory
        @update:model-value="toggleTheme"
      >
        <v-row no-gutters>
          <v-col
            cols="4"
            sm="3"
            md="2"
            class="pa-2"
            v-for="theme in themeOptions"
          >
            <theme-option
              :key="theme.name"
              :text="theme.name"
              :icon="theme.icon"
            />
          </v-col>
        </v-row>
      </v-item-group>
    </template>
  </r-section>
</template>
