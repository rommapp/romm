<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    icon: string;
  }>(),
  { title: "", icon: "" }
);
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">{{ icon }}</v-icon>
        {{ title }}
      </v-toolbar-title>
      <slot name="toolbar-append"></slot>
    </v-toolbar>

    <v-divider />

    <!-- Check style card-text -->
    <v-card-text class="pa-1">
      <slot name="content"></slot>
    </v-card-text>
  </v-card>
</template>
