<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const authStore = storeAuth();
const platformsVersions = configStore.value.PLATFORMS_VERSIONS;
const editable = ref(false);
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-gamepad-variant</v-icon>
        Platforms Versions
      </v-toolbar-title>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        class="ma-2"
        rounded="0"
        size="small"
        variant="text"
        @click="editable = !editable"
        icon="mdi-cog"
      >
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-1">
      <v-row no-gutters class="align-center">
        <v-col
          cols="6"
          sm="4"
          md="3"
          lg="2"
          xl="2"
          v-for="(slug, fsSlug) in platformsVersions"
          :key="slug"
          :title="slug"
        >
          <v-list-item class="bg-terciary ma-1 pa-1 text-truncate">
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="40" class="mx-2">
                <platform-icon class="platform-icon" :key="slug" :slug="slug" />
              </v-avatar>
            </template>
            <v-list-item class="bg-primary pr-2 pl-2">
              <span>{{ fsSlug }}</span>
              <template v-slot:append>
                <v-slide-x-reverse-transition>
                  <v-btn
                    v-if="
                      authStore.scopes.includes('platforms.write') && editable
                    "
                    rounded="0"
                    variant="text"
                    size="x-small"
                    icon="mdi-pencil"
                    @click="
                      emitter?.emit('showCreatePlatformVersionDialog', {
                        fsSlug,
                        slug,
                      })
                    "
                    class="ml-2"
                  />
                </v-slide-x-reverse-transition>
                <v-slide-x-reverse-transition>
                  <v-btn
                    v-if="
                      authStore.scopes.includes('platforms.write') && editable
                    "
                    rounded="0"
                    variant="text"
                    size="x-small"
                    icon="mdi-delete"
                    @click="
                      emitter?.emit('showDeletePlatformVersionDialog', {
                        fsSlug,
                        slug,
                      })
                    "
                    class="text-romm-red"
                  />
                </v-slide-x-reverse-transition>
              </template>
            </v-list-item>
          </v-list-item>
        </v-col>
        <v-col cols="6" sm="4" md="3" lg="2" xl="2" class="px-1">
          <v-expand-transition>
            <v-btn
              v-if="authStore.scopes.includes('platforms.write') && editable"
              block
              rounded="0"
              size="large"
              prepend-icon="mdi-plus"
              variant="outlined"
              class="text-romm-accent-1"
              @click="
                emitter?.emit('showCreatePlatformVersionDialog', {
                  fsSlug: '',
                  slug: '',
                })
              "
            >
              Add
            </v-btn>
          </v-expand-transition>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.platform-icon {
  cursor: pointer;
}
</style>
