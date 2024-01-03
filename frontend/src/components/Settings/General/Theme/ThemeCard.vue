<script setup lang="ts">
import { ref } from "vue";
import { useTheme } from "vuetify";
import { themes, autoThemeKey } from "@/styles/themes";
import ThemeOption from "@/components/Settings/General/Theme/ThemeOption.vue";

const theme = useTheme();
const storedTheme = parseInt(localStorage.getItem("settings.theme") ?? "");
const selectedTheme = ref(isNaN(storedTheme) ? autoThemeKey : storedTheme);

// Functions
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
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-brush-variant</v-icon>
        Theme
      </v-toolbar-title>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-3">
      <v-item-group
        mandatory
        v-model="selectedTheme"
        @update:model-value="toggleTheme"
      >
        <v-row no-gutters>
          <theme-option
            key="dark"
            value="dark"
            icon="mdi-moon-waning-crescent"
          />
          <theme-option
            key="light"
            value="light"
            icon="mdi-white-balance-sunny"
          />
          <theme-option key="auto" value="auto" icon="mdi-theme-light-dark" />
        </v-row>
      </v-item-group>
    </v-card-text>
  </v-card>
</template>
