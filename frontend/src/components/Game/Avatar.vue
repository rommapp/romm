<script setup lang="ts">
withDefaults(defineProps<{ src: string; size?: number }>(), { size: 45 });
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <v-img :src="src" />
  </v-avatar>
</template>
