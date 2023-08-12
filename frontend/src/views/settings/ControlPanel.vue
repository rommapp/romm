<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import version from "../../../package";

// Props
const tab = ref("ui");
const theme = useTheme();
const darkMode =
  localStorage.getItem("theme") == "rommDark" ? ref(true) : ref(false);
const ROMM_VERSION = version.version;

// Functions
function toggleTheme() {
  theme.global.name.value = darkMode.value ? "rommDark" : "rommLight";
  darkMode.value
    ? localStorage.setItem("theme", "rommDark")
    : localStorage.setItem("theme", "rommLight");
}
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="rommAccent1" class="bg-primary">
      <v-tab value="general" rounded="0">
        General
      </v-tab>
      <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
  </v-app-bar>

  <v-window v-model="tab">
    <v-window-item value="general">
      <v-row class="pa-4 bg-red" no-gutters>
        <v-card>
          <v-toolbar density="compact" class="bg-primary">
            <v-row class="align-center" no-gutters>
              <v-col cols="9" xs="9" sm="10" md="10" lg="11">
                <v-icon icon="mdi-pencil-box" class="ml-5" />
              </v-col>
              <v-col>
                <v-btn
                  @click="show = false"
                  class="bg-primary"
                  rounded="0"
                  variant="text"
                  icon="mdi-close"
                  block
                />
              </v-col>
            </v-row>
          </v-toolbar>
        </v-card>
      </v-row>
    </v-window-item>

    <v-window-item value="ui">
      <v-row class="pa-4" no-gutters>
        <v-switch
          @change="toggleTheme()"
          v-model="darkMode"
          prepend-icon="mdi-theme-light-dark"
          hide-details
          inset
        />
      </v-row>
    </v-window-item>
  </v-window>

  <v-bottom-navigation :elevation="0" height="36" class="text-caption">
    <v-row class="align-center justify-center" no-gutters>
      <span class="text-rommAccent1">RomM</span>
      <span class="ml-1">{{ ROMM_VERSION }}</span>
    </v-row>
  </v-bottom-navigation>
</template>
