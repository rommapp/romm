<script setup>
import { ref, inject } from "vue";
import storePlatforms from "@/stores/platforms";
import DrawerHeader from "@/components/Drawer/Header.vue";
import PlatformListItem from "@/components/Platform/PlatformListItem.vue";
import LogoutBtn from "@/components/Drawer/LogoutBtn.vue";

// Props
const platforms = storePlatforms();
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
    width="300"
    rail-width="105"
    elevation="0"
  >
    <template v-slot:prepend>
      <drawer-header :rail="rail" />
    </template>
    <v-list v-model:opened="open" class="pa-0">
      <v-divider />

      <v-list-group value="Platforms">
        <template v-slot:activator="{ props }">
          <v-list-item v-bind="props">
            <span class="text-body-1 text-truncate">{{
              rail ? "" : "Platforms"
            }}</span>
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40"
                ><v-icon>mdi-controller</v-icon></v-avatar
              >
            </template>
          </v-list-item>
        </template>
        <platform-list-item
          class="drawer-item"
          v-for="platform in platforms.value"
          :platform="platform"
          :rail="rail"
          :key="platform.slug"
        />
      </v-list-group>

      <v-list-group value="Library">
        <template v-slot:activator="{ props }">
          <v-list-item v-bind="props">
            <span class="text-body-1 text-truncate">{{
              rail ? "" : "Library"
            }}</span>
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40"
                ><v-icon>mdi-animation-outline</v-icon></v-avatar
              >
            </template>
          </v-list-item>
        </template>
        <v-list-item class="drawer-item bg-terciary" to="/library/scan">
          <span class="text-body-2 text-truncate">{{
            rail ? "" : "Scan"
          }}</span>
          <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"
              ><v-icon>mdi-magnify-scan</v-icon></v-avatar
            >
          </template>
        </v-list-item>
        <v-list-item class="drawer-item bg-terciary" disabled>
          <span class="text-body-2 text-truncate">{{
            rail ? "" : "Upload"
          }}</span>
          <span class="text-caption text-truncate ml-1">{{
            rail ? "" : "[coming soon]"
          }}</span>
          <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"
              ><v-icon>mdi-upload</v-icon></v-avatar
            >
          </template>
        </v-list-item>
      </v-list-group>

      <v-list-group value="Settings">
        <template v-slot:activator="{ props }">
          <v-list-item v-bind="props">
            <span class="text-body-1 text-truncate">{{
              rail ? "" : "Settings"
            }}</span>
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40"
                ><v-icon>mdi-cog</v-icon></v-avatar
              >
            </template>
          </v-list-item>
        </template>
        <v-list-item
          class="drawer-item bg-terciary"
          to="/settings/control-panel"
        >
          <span class="text-body-2 text-truncate">{{
            rail ? "" : "Control panel"
          }}</span>
          <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"
              ><v-icon>mdi-view-dashboard</v-icon></v-avatar
            >
          </template>
        </v-list-item>
      </v-list-group>
    </v-list>

    <template v-slot:append>
      <v-divider class="border-opacity-25" :thickness="1" />
      <logout-btn :rail="rail" />
    </template>
  </v-navigation-drawer>
</template>

<style scoped>
.drawer-item {
  padding-inline-start: 30px !important;
}
</style>
