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
        Platforms Binding
      </v-toolbar-title>
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter.emit('showCreatePlatformBindingDialog')"
      >
        Add Binding
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-row no-gutters>
        <v-chip-group v-for="(platform, fs_platform) in platformsBinding">
          <v-chip class="my-0 py-7 bg-primary" label>
            <v-avatar class="mr-3 py-2" :rounded="0" size="70">
              <platform-icon :platform="platform" />
            </v-avatar>
            <v-chip class="bg-secondary" label>
              <span>{{ fs_platform }}</span>
            </v-chip>
          </v-chip>
        </v-chip-group>
      </v-row>
    </v-card-text>
  </v-card>

  <create-platform-binding-dialog />
</template>

<style scoped></style>
