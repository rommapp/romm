<script setup>
import { ref, onBeforeMount, inject } from "vue";
import { api } from "@/services/api";
import storeHeartbeat from "@/stores/heartbeat";
// import CreateExclusionDialog from "@/components/Dialog/Platform/CreateExclusion.vue";

// Props
const emitter = inject("emitter");
const heartbeat = storeHeartbeat();
const excluded_platforms = heartbeat.data.CONFIG.EXCLUDED_PLATFORMS;
const excludad_single_roms_files = heartbeat.data.CONFIG.EXCLUDED_SINGLE_FILES;
const excludad_single_roms_ext = heartbeat.data.CONFIG.EXCLUDED_SINGLE_EXT;
const excludad_multi_roms_files = heartbeat.data.CONFIG.EXCLUDED_MULTI_FILES;
const excludad_multi_roms_parts_files =
  heartbeat.data.CONFIG.EXCLUDED_MULTI_PARTS_FILES;
const excludad_multi_roms_parts_ext =
  heartbeat.data.CONFIG.EXCLUDED_MULTI_PARTS_EXT;
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-cancel</v-icon>
        Excluded
      </v-toolbar-title>
      <v-btn
        disabled
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter.emit('showCreateExclusionDialog')"
      >
        Add
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
        <v-row no-gutters class="mb-3">
          <v-col class="pa-1">
            <v-chip label class="mx-1" v-for="excluded in excluded_platforms">{{
              excluded
            }}</v-chip>
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Single Roms Files
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters class="mb-3">
          <v-col class="pa-1">
            <v-chip
              label
              class="mx-1"
              v-for="excluded in excludad_single_roms_files"
              >{{ excluded }}</v-chip
            >
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Single Roms Extensions
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters class="mb-3">
          <v-col class="pa-1">
            <v-chip
              label
              class="mx-1"
              v-for="excluded in excludad_single_roms_ext"
              >{{ excluded }}</v-chip
            >
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Multi Roms Files
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters class="mb-3">
          <v-col class="pa-1">
            <v-chip
              label
              class="mx-1"
              v-for="excluded in excludad_multi_roms_files"
              >{{ excluded }}</v-chip
            >
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Multi Roms Parts Files
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters class="mb-3">
          <v-col class="pa-1">
            <v-chip
              label
              class="mx-1"
              v-for="excluded in excludad_multi_roms_parts_files"
              >{{ excluded }}</v-chip
            >
          </v-col>
        </v-row>
      </v-row>

      <v-row no-gutters class="bg-terciary mt-1 mb-2 px-3">
        <v-toolbar-title class="pa-2 text-body-1">
          <v-icon>mdi-file-document-remove-outline</v-icon>
          Multi Roms Parts Extensions
        </v-toolbar-title>
        <v-divider class="border-opacity-25 mb-1" />
        <v-row no-gutters class="mb-3">
          <v-col class="pa-1">
            <v-chip
              label
              class="mx-1"
              v-for="excluded in excludad_multi_roms_parts_ext"
              >{{ excluded }}</v-chip
            >
          </v-col>
        </v-row>
      </v-row>
    </v-card-text>
  </v-card>

  <!-- <create-exclusions-dialog /> -->
</template>

<style scoped></style>
