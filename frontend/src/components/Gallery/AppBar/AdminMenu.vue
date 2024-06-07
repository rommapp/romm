<script setup lang="ts">
import ScanBtn from "@/components/Gallery/AppBar/ScanBtn.vue";
import UploadRomBtn from "@/components/Gallery/AppBar/UploadRomBtn.vue";
import ViewFirmwareBtn from "@/components/Gallery/AppBar/ViewFirmwareBtn.vue";
import DeleteBtn from "@/components/Gallery/AppBar/DeleteBtn.vue";
</script>

<template>
  <v-list
    rounded="0"
    class="pa-0"
  >
    <upload-rom-btn />
    <view-firmware-btn />
    <scan-btn />
    <v-divider class="border-opacity-25" />
    <delete-btn />
  </v-list>
</template>
