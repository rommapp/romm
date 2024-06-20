<script setup lang="ts">
withDefaults(
  defineProps<{
    enabled: boolean;
    title?: string;
    description?: string;
    icon?: string;
  }>(),
  { title: "", description: "", icon: "" }
);
</script>
<template>
  <v-card elevation="0" :disabled="!enabled">
    <v-list-item class="pa-0">
      <v-list-item-title
        class="font-weight-bold"
        :class="{ 'text-romm-accent-1': enabled }"
        >{{ title }}</v-list-item-title
      >
      <v-list-item-subtitle>{{ description }}</v-list-item-subtitle>
      <template #prepend
        ><v-icon
          :class="enabled ? 'text-romm-accent-1' : ''"
          :icon="icon" /></template
    ></v-list-item>
  </v-card>
</template>
