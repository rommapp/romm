<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 40 });
</script>

<template>
  <v-avatar :size="size">
    <img src="/assets/isotipo.svg" :width="size" />
  </v-avatar>
</template>
