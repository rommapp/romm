<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import api from "@/services/api";
import storeHeartbeat from "@/stores/heartbeat";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import CreatePlatformBindingDialog from "@/components/Dialog/Platform/CreatePlatformBinding.vue";
import DeletePlatformBindingDialog from "@/components/Dialog/Platform/DeletePlatformBinding.vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const platformsBinding = heartbeat.data.CONFIG.PLATFORMS_BINDING;

// Functions
function addBindPlatform(fsSlug: string, slug: string) {
  api.addPlatformBindConfig({ fsSlug: fsSlug, slug: slug });
}
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
        @click="emitter?.emit('showCreatePlatformBindingDialog', null)"
      >
        Add
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-1">
      <v-row no-gutters>
        <v-col
          cols="6"
          sm="3"
          md="2"
          lg="2"
          v-for="platform in Object.keys(platformsBinding)"
          :key="platform"
        >
          <v-list-item class="bg-terciary ma-1 pa-1">
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40" class="mr-1">
                <platform-icon :platform="platformsBinding[platform]" />
              </v-avatar>
            </template>
            <div
              class="bg-primary pa-2 text-caption text-truncate"
              :title="platform"
            >
              <span clas="pa-1">{{ platform }}</span>
            </div>
            <template v-slot:append>
              <v-btn
                rounded="0"
                variant="text"
                size="small"
                icon="mdi-delete"
                @click="
                  emitter?.emit('showDeletePlatformBindingDialog', platform)
                "
                class="text-romm-red ml-1"
              />
            </template>
          </v-list-item>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <create-platform-binding-dialog />
  <delete-platform-binding-dialog />
</template>

<style scoped></style>
