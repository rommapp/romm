<script setup lang="ts">
import { type SimpleRom } from "@/stores/roms.js";
import { ref } from "vue";

const props = defineProps<{ rom: SimpleRom }>();
const fav = ref(false);

// Functions
function addToFavs() {
  fav.value = !fav.value;
}
</script>

<template>
  <v-btn
    @click.stop="addToFavs"
    class="translucent text-shadow"
    rouded="0"
    size="x-small"
    variant="text"
    icon
    ><v-icon color="romm-accent-1">{{
      fav ? "mdi-star" : "mdi-star-outline"
    }}</v-icon></v-btn
  >
</template>
