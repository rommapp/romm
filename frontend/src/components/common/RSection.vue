<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    icon: string;
    titleDivider?: boolean;
    iconColor?: string;
    bgColor?: string;
  }>(),
  {
    title: "",
    icon: "",
    titleDivider: false,
    iconColor: "",
    bgColor: "bg-background",
  },
);
</script>

<template>
  <v-card class="bg-background" elevation="0">
    <v-toolbar class="bg-toplayer px-1" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon :color="iconColor" class="mr-2">
          {{ icon }}
        </v-icon>
        {{ title }}
        <slot name="toolbar-title-append" />
      </v-toolbar-title>
      <slot name="toolbar-append" />
    </v-toolbar>

    <v-divider v-if="titleDivider" />

    <!-- Check style card-text -->
    <v-card-text :class="['pa-0', bgColor]">
      <slot name="content" />
    </v-card-text>
  </v-card>
</template>
