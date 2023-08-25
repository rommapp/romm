<script setup>
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import Users from "@/views/Settings/Users/Users.vue";
import Theme from "@/views/Settings/UserInterface/Theme.vue";
import version from "../../../package";

// Props
const auth = storeAuth();
const tab = ref(auth.scopes.includes("users.read") ? "users" : "ui");
const ROMM_VERSION = version.version;
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="romm-accent-1" class="bg-primary">
      <v-tab
        :disabled="!auth.scopes.includes('users.read')"
        value="users"
        rounded="0"
      >
        Users
      </v-tab>
      <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
  </v-app-bar>

  <v-window v-model="tab">
    <!-- Users tab -->
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
      <span class="text-romm-accent-1">RomM</span>
      <span class="ml-1">{{ ROMM_VERSION }}</span>
    </v-row>
  </v-bottom-navigation>
</template>
