<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import ScanBtn from "@/components/Gallery/AppBar/ScanBtn.vue";
import UploadRomBtn from "@/components/Gallery/AppBar/UploadRomBtn.vue";
import DeleteBtn from "@/components/Gallery/AppBar/DeleteBtn.vue";

const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <upload-rom-btn />
    <v-divider class="border-opacity-25" />
    <scan-btn />
    <v-divider class="border-opacity-25" />
    <delete-btn />
  </v-list>
</template>
