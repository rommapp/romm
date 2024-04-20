<script setup lang="ts">
import storeConfig from "@/stores/config";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const authStore = storeAuth();
const excluded_platforms = configStore.value.EXCLUDED_PLATFORMS;
const excludad_single_roms_files = configStore.value.EXCLUDED_SINGLE_FILES;
const excludad_single_roms_ext = configStore.value.EXCLUDED_SINGLE_EXT;
const excludad_multi_roms_files = configStore.value.EXCLUDED_MULTI_FILES;
const excludad_multi_roms_parts_files =
  configStore.value.EXCLUDED_MULTI_PARTS_FILES;
const excludad_multi_roms_parts_ext =
  configStore.value.EXCLUDED_MULTI_PARTS_EXT;
const editable = ref(false);
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-cancel</v-icon>
        Excluded
      </v-toolbar-title>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        class="ma-2"
        rounded="0"
        size="small"
        variant="text"
        @click="editable = !editable"
        icon="mdi-cog"
        disabled
      >
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-1">
      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-controller-off</v-icon>
          Platforms
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters>
          <v-col class="pa-1">
            <v-chip label class="ma-1" v-for="excluded in excluded_platforms">{{
              excluded
            }}</v-chip>
            <v-expand-transition>
              <v-btn
                v-if="authStore.scopes.includes('platforms.write') && editable"
                rounded="1"
                prepend-icon="mdi-plus"
                variant="outlined"
                class="text-romm-accent-1 ml-1"
                @click="
                  emitter?.emit('showCreateExclusionDialog', {
                    exclude: 'platforms',
                  })
                "
              >
                Add
              </v-btn>
            </v-expand-transition>
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Single Roms Files
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters>
          <v-col class="pa-1">
            <v-chip
              label
              class="ma-1"
              v-for="excluded in excludad_single_roms_files"
              >{{ excluded }}</v-chip
            >
            <v-expand-transition>
              <v-btn
                v-if="authStore.scopes.includes('platforms.write') && editable"
                rounded="1"
                prepend-icon="mdi-plus"
                variant="outlined"
                class="text-romm-accent-1 ml-1"
              >
                Add
              </v-btn>
            </v-expand-transition>
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Single Roms Extensions
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters>
          <v-col class="pa-1">
            <v-chip
              label
              class="ma-1"
              v-for="excluded in excludad_single_roms_ext"
              >{{ excluded }}</v-chip
            >
            <v-expand-transition>
              <v-btn
                v-if="authStore.scopes.includes('platforms.write') && editable"
                rounded="1"
                prepend-icon="mdi-plus"
                variant="outlined"
                class="text-romm-accent-1 ml-1"
              >
                Add
              </v-btn>
            </v-expand-transition>
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Multi Roms Files
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters>
          <v-col class="pa-1">
            <v-chip
              label
              class="ma-1"
              v-for="excluded in excludad_multi_roms_files"
              >{{ excluded }}</v-chip
            >
            <v-expand-transition>
              <v-btn
                v-if="authStore.scopes.includes('platforms.write') && editable"
                rounded="1"
                prepend-icon="mdi-plus"
                variant="outlined"
                class="text-romm-accent-1 ml-1"
              >
                Add
              </v-btn>
            </v-expand-transition>
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Multi Roms Parts Files
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters>
          <v-col class="pa-1">
            <v-chip
              label
              class="ma-1"
              v-for="excluded in excludad_multi_roms_parts_files"
              >{{ excluded }}</v-chip
            >
            <v-expand-transition>
              <v-btn
                v-if="authStore.scopes.includes('platforms.write') && editable"
                rounded="1"
                prepend-icon="mdi-plus"
                variant="outlined"
                class="text-romm-accent-1 ml-1"
              >
                Add
              </v-btn>
            </v-expand-transition>
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Multi Roms Parts Extensions
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters>
          <v-col class="pa-1">
            <v-chip
              label
              class="ma-1"
              v-for="excluded in excludad_multi_roms_parts_ext"
              >{{ excluded }}</v-chip
            >
            <v-expand-transition>
              <v-btn
                v-if="authStore.scopes.includes('platforms.write') && editable"
                rounded="1"
                prepend-icon="mdi-plus"
                variant="outlined"
                class="text-romm-accent-1 ml-1"
              >
                Add
              </v-btn>
            </v-expand-transition>
          </v-col>
        </v-row>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style scoped></style>
