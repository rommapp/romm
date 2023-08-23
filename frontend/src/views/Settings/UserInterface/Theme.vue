<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import { themes } from "@/styles/themes";

// Props
const theme = useTheme();
const selectedTheme = ref(localStorage.getItem("theme"));

// Functions
function toggleTheme() {
  localStorage.setItem("theme", selectedTheme.value);
  theme.global.name.value = themes[selectedTheme.value];
}
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button"
        ><v-icon class="mr-3">mdi-theme-light-dark</v-icon
        >Theme</v-toolbar-title
      >
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-item-group
        mandatory
        v-model="selectedTheme"
        @update:model-value="toggleTheme"
      >
        <v-row no-gutters>
          <v-col key="dark" cols="6" sm="3" md="2" lg="2" class="px-2">
            <v-item v-slot="{ isSelected, toggle }">
              <v-card
                :color="isSelected ? 'romm-accent-1' : 'romm-gray'"
                class="d-flex align-center"
                height="50"
                variant="outlined"
                @click="toggle"
              >
                <v-scroll-y-transition>
                  <div class="text-subtitle-2 flex-grow-1 text-center">
                    <v-icon class="mr-2">mdi-moon-waning-crescent</v-icon>Dark
                    Theme
                  </div>
                </v-scroll-y-transition>
              </v-card>
            </v-item>
          </v-col>
          <v-col key="light" cols="6" sm="3" md="2" lg="2" class="px-2">
            <v-item v-slot="{ isSelected, toggle }">
              <v-card
                :color="isSelected ? 'romm-accent-1' : 'romm-gray'"
                class="d-flex align-center"
                height="50"
                variant="outlined"
                @click="toggle"
              >
                <v-scroll-y-transition>
                  <div class="text-subtitle-2 flex-grow-1 text-center">
                    <v-icon class="mr-2">mdi-weather-sunny</v-icon>Light Theme
                  </div>
                </v-scroll-y-transition>
              </v-card>
            </v-item>
          </v-col>
        </v-row>
      </v-item-group>
    </v-card-text>
  </v-card>
</template>
