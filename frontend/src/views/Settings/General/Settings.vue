<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import { themes, autoThemeKey } from "@/styles/themes";
import SettingsItem from "@/views/Settings/General/SettingsItem.vue";

// Props
const theme = useTheme();
const selectedTheme = ref(
  parseInt(localStorage.getItem("settings.theme")) || autoThemeKey
);

// Functions
function toggleTheme() {
  localStorage.setItem("settings.theme", selectedTheme.value);

  const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
  if (selectedTheme.value === autoThemeKey) {
    theme.global.name.value = mediaMatch.matches ? "dark" : "light";
  } else {
    theme.global.name.value = themes[selectedTheme.value];
  }
}
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-theme-light-dark</v-icon>
        Theme
      </v-toolbar-title>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-item-group
        mandatory
        v-model="selectedTheme"
        @update:model-value="toggleTheme"
      >
        <v-row no-gutters>
          <settings-item
            key="dark"
            value="dark"
            icon="mdi-moon-waning-crescent"
          />
          <settings-item
            key="light"
            value="light"
            icon="mdi-white-balance-sunny"
          />
          <settings-item key="auto" value="auto" icon="mdi-theme-light-dark" />
        </v-row>
      </v-item-group>
    </v-card-text>
  </v-card>
</template>
