<script setup>
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import Users from "@/views/Settings/General/Users.vue";
import Theme from "@/views/Settings/UserInterface/Theme.vue";
import version from "../../../package";

// Props
const tab = ref("general");
const auth = storeAuth();
const ROMM_VERSION = version.version;
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="rommAccent1" class="bg-primary">
      <v-tab v-if="auth?.user" value="users" rounded="0">Users</v-tab>
      <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
  </v-app-bar>

  <!-- Users tab -->
  <v-window v-model="tab">
    <v-window-item value="users">
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
