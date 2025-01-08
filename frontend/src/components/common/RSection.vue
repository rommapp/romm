<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    icon: string;
    iconColor?: string;
  }>(),
  { title: "", icon: "", iconColor: "" },
);
</script>

<template>
  <v-card class="ma-2 bg-background" elevation="0">
    <v-toolbar class="bg-toplayer rounded px-1" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon :color="iconColor" class="mr-2">{{ icon }}</v-icon>
        {{ title }}
      </v-toolbar-title>
      <slot name="toolbar-append"></slot>
    </v-toolbar>

    <!-- Check style card-text -->
    <v-card-text class="pa-0 bg-background">
      <slot name="content"></slot>
    </v-card-text>
  </v-card>
</template>
