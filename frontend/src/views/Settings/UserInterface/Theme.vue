<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import { themes } from "@/styles/themes.js";

const selectedTheme = ref(localStorage.getItem("theme"));
function toggleTheme() {
  localStorage.setItem("theme", selectedTheme.value);
  useTheme().global.name.value = themes[selectedTheme.value];
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
        :on-update:model-value="toggleTheme()"
      >
        <v-radio-group v-model="selectedTheme" hide-details>
          <v-row no-gutters>
            <v-col key="dark" cols="6" sm="3" md="2" lg="2" class="px-2">
              <v-item v-slot="{ isSelected, toggle }">
                <v-card
                  :color="isSelected ? 'terciary' : 'primary'"
                  class="d-flex align-center"
                  height="70"
                  @click="toggle"
                >
                  <v-scroll-y-transition>
                    <div class="text-subtitle-2 flex-grow-1 text-center">
                      <v-icon class="mr-2">mdi-moon-waning-crescent</v-icon>Dark
                      Theme
                      <v-radio
                        :value="0"
                        class="position-absolute"
                        style="bottom: 1rem; right: 1rem"
                      />
                    </div>
                  </v-scroll-y-transition>
                </v-card>
              </v-item>
            </v-col>
            <v-col key="light" cols="6" sm="3" md="2" lg="2" class="px-2">
              <v-item v-slot="{ isSelected, toggle }">
                <v-card
                  :color="isSelected ? 'terciary' : 'primary'"
                  class="d-flex align-center"
                  height="70"
                  @click="toggle"
                >
                  <v-scroll-y-transition>
                    <div class="text-subtitle-2 flex-grow-1 text-center">
                      <v-icon class="mr-2">mdi-weather-sunny</v-icon>Light Theme
                      <v-radio
                        :value="1"
                        class="position-absolute"
                        style="bottom: 1rem; right: 1rem"
                      />
                    </div>
                  </v-scroll-y-transition>
                </v-card>
              </v-item>
            </v-col>
          </v-row>
        </v-radio-group>
      </v-item-group>
    </v-card-text>
  </v-card>
</template>
