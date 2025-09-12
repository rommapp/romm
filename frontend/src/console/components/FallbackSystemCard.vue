<script setup lang="ts">
import { computed } from "vue";
import { useConsoleTheme } from "@/console/composables/useConsoleTheme";
import { useThemeAssets } from "@/console/composables/useThemeAssets";

defineProps<{ platformName: string }>();

const { getSystemImagePath } = useThemeAssets();
const themeStore = useConsoleTheme();

const defaultSystemImagePath = computed(
  () => getSystemImagePath("default").value,
);
</script>

<template>
  <v-img
    v-if="themeStore.themeName === 'default'"
    :src="defaultSystemImagePath"
  >
    <div class="w-[66%] h-100">
      <div
        class="h-100 w-100 font-bold text-center px-2 pt-5 pb-4 text-2xl uppercase overflow-hidden text-ellipsis whitespace-nowrap"
        :style="{
          color: 'var(--system-accent)',
          textShadow:
            '0 -3rem 0 #372869, 0 -1.5rem 0 #372869, 0 1.5rem 0 #372869, 0 3rem 0 #372869, 0 4.5rem 0 #372869, 0 6rem 0 #372869, 0 7.5rem 0 #372869',
        }"
      >
        {{ platformName }}
      </div>
    </div>
  </v-img>
  <div v-else class="flex items-center justify-center h-100 pb-5 pt-1 px-1">
    <div class="text-4xl font-bold text-white uppercase">
      {{ platformName }}
    </div>
  </div>
</template>
