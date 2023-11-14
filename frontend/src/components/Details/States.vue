<script setup>
import { formatBytes } from "@/utils/utils";

const props = defineProps(["rom"]);
</script>
<template>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      v-for="state in rom.states"
      :key="state.id"
      :title="state.file_name"
      :subtitle="formatBytes(state.file_size_bytes)"
    >
      <template v-slot:append>
        <v-btn icon :href="state.download_path" download>
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn icon disabled>
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </template>
    </v-list-item>
  </v-list>
</template>
