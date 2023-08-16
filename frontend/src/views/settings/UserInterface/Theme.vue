<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
const theme = useTheme();
const darkMode =
  localStorage.getItem("theme") == "rommDark" ? ref(true) : ref(false);

// Functions
function toggleTheme() {
  theme.global.name.value = darkMode.value ? "rommDark" : "rommLight";
  darkMode.value
    ? localStorage.setItem("theme", "rommDark")
    : localStorage.setItem("theme", "rommLight");
}
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="comfortable">
      <v-toolbar-title
        ><v-icon class="mr-3">mdi-theme-light-dark</v-icon
        >Theme</v-toolbar-title
      >
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-switch
        @change="toggleTheme()"
        v-model="darkMode"
        hide-details
        inset
        :label="darkMode ? 'Dark' : 'Light'"
      />
    </v-card-text>
  </v-card>
</template>
