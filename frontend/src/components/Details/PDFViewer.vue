<script setup lang="ts">
import VuePdfApp from "vue3-pdf-app";
import { useTheme, useDisplay } from "vuetify";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

defineProps<{ rom: DetailedRom }>();
const { xs } = useDisplay();
const theme = useTheme();
const pdfViewerConfig = {
  sidebarToggle: "sidebarToggleId",
  pageNumber: "pageNumberId",
  numPages: "numPagesId",
  zoomIn: "zoomInId",
  zoomOut: "zoomOutId",
  firstPage: "firstPageId",
  previousPage: "previousPageId",
  nextPage: "nextPageId",
  lastPage: "lastPageId",
  download: "downloadId",
};
</script>

<template>
  <v-toolbar class="bg-toplayer px-2" density="compact" :elevation="0">
    <button
      :id="pdfViewerConfig.sidebarToggle"
      class="pdfv-toolbar-btn"
      type="button"
    >
      <v-icon>mdi-menu</v-icon>
    </button>
    <v-spacer />

    <input
      :id="pdfViewerConfig.pageNumber"
      class="px-1"
      style="width: 40px"
      type="number"
    />
    <span :id="pdfViewerConfig.numPages" class="ml-2" />
    <button
      :id="pdfViewerConfig.firstPage"
      class="pdfv-toolbar-btn"
      :class="{ 'ml-8': !xs, 'ml-4': xs }"
      type="button"
    >
      <v-icon>mdi-page-first</v-icon>
    </button>

    <button
      v-show="!xs"
      :id="pdfViewerConfig.previousPage"
      class="pdfv-toolbar-btn"
      type="button"
    >
      <v-icon>mdi-chevron-left</v-icon>
    </button>
    <button
      v-show="!xs"
      :id="pdfViewerConfig.nextPage"
      class="pdfv-toolbar-btn"
      type="button"
    >
      <v-icon>mdi-chevron-right</v-icon>
    </button>

    <button
      :id="pdfViewerConfig.lastPage"
      class="pdfv-toolbar-btn"
      type="button"
    >
      <v-icon>mdi-page-last</v-icon>
    </button>
    <button
      :id="pdfViewerConfig.zoomIn"
      class="pdfv-toolbar-btn"
      :class="{ 'ml-8': !xs, 'ml-4': xs }"
      type="button"
    >
      <v-icon>mdi-magnify-plus-outline</v-icon>
    </button>
    <button
      :id="pdfViewerConfig.zoomOut"
      class="pdfv-toolbar-btn"
      type="button"
    >
      <v-icon>mdi-magnify-minus-outline</v-icon>
    </button>
    <v-spacer />
    <button
      :id="pdfViewerConfig.download"
      class="pdfv-toolbar-btn"
      type="button"
    >
      <v-icon>mdi-download</v-icon>
    </button>
  </v-toolbar>
  <VuePdfApp
    :id-config="pdfViewerConfig"
    :config="{ toolbar: false }"
    :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
    style="height: 100dvh"
    :pdf="`${FRONTEND_RESOURCES_PATH}/${rom.path_manual}`"
  />
</template>

<style scoped>
/* the vue-pdf-app needs to be styled because it only accepts basic html elements */
.pdf-app.light,
.pdf-app.dark {
  --pdf-app-background-color: rgba(var(--v-theme-surface)) !important;
}

input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

input[type="number"] {
  -moz-appearance: textfield;
  appearance: textfield;
  text-align: right;
  padding-left: 1px;
  padding-right: 1px;
  border: 1px solid rgba(var(--v-theme-secondary));
  border-radius: 5px;
  -webkit-transition: 0.5s;
  transition: 0.5s;
  outline: none;
}

.pdfv-toolbar-btn {
  transition:
    color 0.15s ease-in-out,
    transform 0.1s ease-in-out background-color 0.15s linear;
  border-radius: 5px;
  padding: 6px;
}

.pdfv-toolbar-btn:hover {
  color: rgba(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-surface));
}

.pdfv-toolbar-btn:active {
  transform: translateY(1px) translateX(1px);
}
</style>
