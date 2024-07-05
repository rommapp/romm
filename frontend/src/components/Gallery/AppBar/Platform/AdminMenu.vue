<script setup lang="ts">
import ScanBtn from "@/components/Gallery/AppBar/Platform/ScanBtn.vue";
import UploadRomBtn from "@/components/Gallery/AppBar/Platform/UploadRomBtn.vue";
import DeleteBtn from "@/components/Gallery/AppBar/Platform/DeleteBtn.vue";
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <upload-rom-btn />
    <scan-btn />
    <v-divider />
    <delete-btn />
  </v-list>
</template>
