<script setup lang="ts">
import { ref } from "vue";

withDefaults(defineProps<{ size?: number; avatar?: boolean }>(), {
  size: 40,
  avatar: true,
});

const logos = {
  xbox: { path: "romm_logo_xbox_one_square.svg", weight: 0.945 },
  ps2: { path: "romm_logo_ps2_square.svg", weight: 0.05 },
  snes: { path: "romm_logo_snes_square.svg", weight: 0.005 },
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
  <v-avatar
    :size="size"
    :class="{ 'rounded-circle': avatar, rounded: !avatar }"
  >
    <img :src="`/assets/logos/${randomLogo}`" alt="Romm Logo" :width="size" />
  </v-avatar>
</template>

<style scoped>
.v-avatar {
  transition:
    filter 0.15s ease-in-out,
    border-radius 0.15s ease-in-out;
}
.v-avatar:hover,
.v-avatar.active {
  filter: drop-shadow(0px 0px 2px rgba(var(--v-theme-primary)));
}
</style>
