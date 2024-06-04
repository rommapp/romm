<script setup lang="ts">
import RFooter from "@/components/ControlPanel/Footer.vue";
import Excluded from "@/layouts/ControlPanel/Config/Excluded.vue";
import PlatformBinding from "@/layouts/ControlPanel/Config/PlatformBinding.vue";
import PlatformVersions from "@/layouts/ControlPanel/Config/PlatformVersions.vue";
import Interface from "@/layouts/ControlPanel/General/Interface.vue";
import Tasks from "@/layouts/ControlPanel/General/Tasks.vue";
import Theme from "@/layouts/ControlPanel/General/Theme.vue";
import Users from "@/layouts/ControlPanel/Users/Users.vue";
import storeAuth from "@/stores/auth";
import { ref } from "vue";

// Props
const auth = storeAuth();
const tab = ref("general");
</script>
<template>
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="romm-accent-1" class="bg-primary">
      <v-tab value="general" rounded="0"> General </v-tab>
      <v-tab
        v-if="auth.scopes.includes('platforms.write')"
        value="config"
        rounded="0"
      >
        Config
      </v-tab>
      <v-tab
        v-if="auth.scopes.includes('users.write')"
        value="users"
        rounded="0"
      >
        Users
      </v-tab>
    </v-tabs>
  </v-app-bar>

  <v-window v-model="tab">
    <v-window-item value="general">
      <theme />
      <interface />
      <tasks v-if="auth.scopes.includes('tasks.run')" />
    </v-window-item>

    <v-window-item value="config">
      <platform-binding />
      <platform-versions />
      <excluded />
    </v-window-item>

    <v-window-item value="users">
      <users />
    </v-window-item>
  </v-window>

  <r-footer />
</template>
