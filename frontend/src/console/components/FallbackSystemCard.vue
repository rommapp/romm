<script setup lang="ts">
import { computed } from "vue";
import { useThemeAssets } from "@/console/composables/useThemeAssets";
import { useConsoleTheme } from "@/stores/consoleTheme";

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
    <div class="grid grid-cols-3 gap-4 h-100">
      <div
        class="col-span-2 font-bold text-center px-2 py-4 text-2xl text-wrap text-balance uppercase"
        :style="{ color: 'var(--system-accent)' }"
      >
        {{ platformName }}
      </div>
      <div class="col-span-1 flex items-center justify-end">
        <div class="text-9xl" style="margin-right: -50%">🎮</div>
      </div>
    </div>
  </v-img>
  <div v-else class="flex items-center justify-center h-100 pb-5 pt-1 px-1">
    <div class="font-bold text-4xl font-bold text-white uppercase">
      {{ platformName }}
    </div>
  </div>
</template>
