<script setup>
import { ref, inject } from "vue";
import storePlatforms from "@/stores/platforms";
import storeAuth from "@/stores/auth";
import DrawerHeader from "@/components/Drawer/Header.vue";
import PlatformListItem from "@/components/Platform/PlatformListItem.vue";
import RailFooter from "@/components/Drawer/Footer.vue";

// Props
const platforms = storePlatforms();
const auth = storeAuth();
const drawer = ref(undefined);
const open = ref(["Platforms", "Library", "Settings"]);
const rail = ref(localStorage.getItem("rail") == "true");

// Event listeners bus
const emitter = inject("emitter");
emitter.on("toggleDrawer", () => {
  drawer.value = !drawer.value;
});
emitter.on("toggleDrawerRail", () => {
  rail.value = !rail.value;
  localStorage.setItem("rail", rail.value);
});
</script>

<template>
  <v-navigation-drawer
    v-model="drawer"
    :rail="rail"
    width="270"
    rail-width="70"
    elevation="0"
  >
    <template v-slot:prepend>
      <drawer-header :rail="rail" />
    </template>
    <v-list v-model:opened="open" class="pa-0">
      <v-divider />

      <v-list-group value="Platforms" fluid>
        <template v-slot:activator="{ props }">
          <v-list-item v-bind="props">
            <span v-if="!rail" class="text-body-1 text-truncate">Platforms</span>
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40"
                ><v-icon>mdi-controller</v-icon></v-avatar
              >
            </template>
          </v-list-item>
        </template>
        <platform-list-item
          v-for="platform in platforms.value"
          :platform="platform"
          :rail="rail"
          :key="platform.slug"
        />
      </v-list-group>

      <v-list-group value="Library" v-if="auth.scopes.includes('roms.write')" fluid>
        <template v-slot:activator="{ props }">
          <v-list-item v-bind="props">
            <span v-if="!rail" class="text-body-1 text-truncate">Library</span>
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40"
                ><v-icon>mdi-animation-outline</v-icon></v-avatar
              >
            </template>
          </v-list-item>
        </template>
        <v-list-item class="bg-terciary" to="/library/scan">
          <span v-if="!rail" class="text-body-2 text-truncate">Scan</span>
          <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"
              ><v-icon>mdi-magnify-scan</v-icon></v-avatar
            >
          </template>
        </v-list-item>
        <v-list-item class="bg-terciary" disabled>
          <span v-if="!rail" class="text-body-2 text-truncate">Upload</span>
          <span v-if="!rail" class="text-caption text-truncate ml-1">[coming soon]</span>
          <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"
              ><v-icon>mdi-upload</v-icon></v-avatar
            >
          </template>
        </v-list-item>
      </v-list-group>

      <v-list-group value="Settings" fluid>
        <template v-slot:activator="{ props }">
          <v-list-item v-bind="props">
            <span v-if="!rail" class="text-body-1 text-truncate">Settings</span>
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40"
                ><v-icon>mdi-cog</v-icon></v-avatar
              >
            </template>
          </v-list-item>
        </template>
        <v-list-item
          class="bg-terciary"
          to="/settings/control-panel"
        >
          <span v-if="!rail" class="text-body-2 text-truncate">Control Panel</span>
          <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"
              ><v-icon>mdi-view-dashboard</v-icon></v-avatar
            >
          </template>
        </v-list-item>
      </v-list-group>
    </v-list>

    <template v-if="auth.enabled" v-slot:append>
      <v-divider class="border-opacity-25" :thickness="1" />
      <rail-footer :rail="rail" />
    </template>
  </v-navigation-drawer>
</template>
