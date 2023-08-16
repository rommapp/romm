<script setup>
import { ref } from "vue";
import Users from "@/views/settings/General/Users.vue";
import Theme from "@/views/settings/UserInterface/Theme.vue";
import version from "../../../package";

// Props
const tab = ref("general");
const ROMM_VERSION = version.version;
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="rommAccent1" class="bg-primary">
      <v-tab value="general" rounded="0"> General </v-tab>
      <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
  </v-app-bar>

  <!-- General tab -->
  <v-window v-model="tab">
    <v-window-item value="general">
      <v-row class="pa-1">
        <v-col>
          <users />
        </v-col>
      </v-row>
    </v-window-item>

    <!-- User Interface tab -->
    <v-window-item value="ui">
      <v-row class="pa-1">
        <v-col>
          <theme />
        </v-col>
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
