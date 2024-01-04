<script setup lang="ts">
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import Settings from "@/views/Settings/ControlPanel/General/Base.vue";
import Config from "@/views/Settings/ControlPanel/Config/Base.vue";
import Users from "@/views/Settings/ControlPanel/Users/Base.vue";
import storeHeartbeat from "@/stores/heartbeat";

// Props
const auth = storeAuth();
const heartbeat = storeHeartbeat();
const tab = ref("general");
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="romm-accent-1" class="bg-primary">
      <v-tab value="general" rounded="0">General</v-tab>
      <v-tab value="config" rounded="0">Config</v-tab>
      <v-tab
        :disabled="!auth.scopes.includes('users.read')"
        value="users"
        rounded="0"
      >
        Users
      </v-tab>
    </v-tabs>
  </v-app-bar>

  <v-window v-model="tab">
    <!-- General tab -->
    <v-window-item value="general">
      <v-row class="pa-1">
        <v-col>
          <settings />
        </v-col>
      </v-row>
    </v-window-item>

    <!-- Config tab -->
    <v-window-item value="config">
      <v-row class="pa-1">
        <v-col>
          <config />
        </v-col>
      </v-row>
    </v-window-item>

    <!-- Users tab -->
    <v-window-item value="users">
      <v-row class="pa-1">
        <v-col>
          <users />
        </v-col>
      </v-row>
    </v-window-item>
  </v-window>

  <v-bottom-navigation :elevation="0" height="36" class="text-caption">
    <v-row class="align-center justify-center" no-gutters>
      <span class="text-romm-accent-1">RomM</span>
      <span class="ml-1">{{ heartbeat.data.VERSION }}</span>
    </v-row>
  </v-bottom-navigation>
</template>
