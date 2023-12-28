<script setup>
import { ref, onBeforeMount, inject } from "vue";
import { api } from "@/services/api";
import storeHeartbeat from "@/stores/heartbeat";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import CreatePlatformBindingDialog from "@/components/Dialog/Platform/CreatePlatformBinding.vue";

// Props
const emitter = inject("emitter");
const heartbeat = storeHeartbeat();
const platformsBinding = heartbeat.data.CONFIG.PLATFORMS_BINDING;
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-controller</v-icon>
        Platforms Bindings
      </v-toolbar-title>
      <v-btn
        disabled
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter.emit('showCreatePlatformBindingDialog')"
      >
        Add
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-1">
      <v-row no-gutters>
        <v-col cols="6" sm="3" md="2" lg="2" v-for="(platform, fs_platform) in platformsBinding">
          <v-card-text class="bg-terciary ma-1 py-1 pl-1 pr-3">
            <v-row class="align-center" no-gutters>
              <v-col cols="5" sm="4" md="5" lg="4">
                <v-avatar class="mx-2" :rounded="0" size="40">
                  <platform-icon :platform="platform" />
                </v-avatar>
              </v-col>
              <v-col cols="7" sm="8" md="7" lg="8">
                <div class="bg-primary pa-2 text-caption text-truncate" :title="fs_platform">
                  <span clas="pa-1">{{ fs_platform }}</span>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <create-platform-binding-dialog />
</template>

<style scoped></style>
