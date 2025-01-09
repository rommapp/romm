<script setup lang="ts">
import { ref } from "vue";

withDefaults(defineProps<{ size?: number }>(), { size: 40 });

const logos = {
  xbox: { path: "romm_logo_xbox_one_circle.svg", weight: 0.945 },
  ps2: { path: "romm_logo_ps2_circle.svg", weight: 0.05 },
  snes: { path: "romm_logo_snes_circle.svg", weight: 0.005 },
};

const getRandomLogo = () => {
  const random = Math.random();
  let sum = 0;

  for (const { path, weight } of Object.values(logos)) {
    sum += weight;
    if (random <= sum) return path;
  }

  return logos.xbox.path;
};

// Easter egg: Random logo on each render
const randomLogo = ref<string>(getRandomLogo());
</script>

<template>
  <v-avatar :size="size">
    <img :src="`/assets/logos/${randomLogo}`" alt="Romm Logo" :width="size" />
  </v-avatar>
</template>
