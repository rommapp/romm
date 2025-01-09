<script setup lang="ts">
import { ref } from "vue";

withDefaults(defineProps<{ size?: number }>(), { size: 40 });

const logos = [
  "romm_logo_xbox_one_circle.svg",
  "romm_logo_ps2_circle.svg",
  "romm_logo_snes_circle.svg",
];

const randomLogo = ref<string>(logos[Math.floor(Math.random() * logos.length)]);
</script>

<template>
  <v-avatar :size="size">
    <img :src="`/assets/logos/${randomLogo}`" alt="Romm Logo" :width="size" />
  </v-avatar>
</template>
