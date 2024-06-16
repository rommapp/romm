<script setup lang="ts">
import RailFooter from "@/components/Drawer/Footer.vue";
import DrawerHeader from "@/components/Drawer/Header.vue";
import PlatformListItem from "@/components/Platform/ListItem.vue";
import ActionBar from "@/components/Drawer/ActionBar.vue";
import storeAuth from "@/stores/auth";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { lgAndUp } = useDisplay();
const platforms = storePlatforms();
const auth = storeAuth();
const drawer = ref(false);
const rail = ref(localStorage.getItem("rail") == "true");

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("toggleDrawer", () => {
  drawer.value = !drawer.value;
});
emitter?.on("toggleDrawerRail", () => {
  rail.value = !rail.value;
  localStorage.setItem("rail", rail.value.toString());
});
</script>

<template>
  <v-navigation-drawer
    v-model="drawer"
    :rail="rail"
    width="250"
    rail-width="80"
    elevation="0"
  >
    <v-list class="py-0">
      <v-list-group value="Platforms" fluid>
        <template #activator="{ props }">
          <v-list-item v-bind="props">
            <span v-if="!rail" class="text-body-1 text-truncate"
              >Platforms</span
            >
            <template #prepend>
              <v-avatar :rounded="0" size="40">
                <v-icon>mdi-controller</v-icon>
              </v-avatar>
            </template>
          </v-list-item>
        </template>
        <platform-list-item
          v-for="platform in platforms.filledPlatforms"
          :key="platform.slug"
          class="py-4"
          :platform="platform"
          :rail="rail"
        />
      </v-list-group>
    </v-list>
    <v-list class="py-0">
      <v-list-group
        v-if="auth.scopes.includes('roms.write')"
        value="Library"
        fluid
      >
        <template #activator="{ props }">
          <v-list-item v-bind="props">
            <span v-if="!rail" class="text-body-1 text-truncate">Library</span>
            <template #prepend>
              <v-avatar :rounded="0" size="40">
                <v-icon>mdi-animation-outline</v-icon>
              </v-avatar>
            </template>
          </v-list-item>
        </template>
        <v-list-item class="bg-terciary" :to="{ name: 'libraryScan' }">
          <span v-if="!rail" class="text-body-2 text-truncate">Scan</span>
          <template #prepend>
            <v-avatar :rounded="0" size="40">
              <v-icon>mdi-magnify-scan</v-icon>
            </v-avatar>
          </template>
        </v-list-item>
        <v-list-item
          v-if="auth.scopes.includes('platforms.write')"
          class="bg-terciary"
          :to="{ name: 'libraryConfig' }"
        >
          <span v-if="!rail" class="text-body-2 text-truncate"
            >Configuration</span
          >
          <template #prepend>
            <v-avatar :rounded="0" size="40">
              <v-icon>mdi-table-cog</v-icon>
            </v-avatar>
          </template>
        </v-list-item>
      </v-list-group>
    </v-list>
  </v-navigation-drawer>
</template>
