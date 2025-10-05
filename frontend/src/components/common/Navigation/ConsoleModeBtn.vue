<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";

withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);

const router = useRouter();
const route = useRoute();

function enterConsoleMode() {
  // Navigate first so route guards run promptly
  router.push({ name: ROUTES.CONSOLE_HOME });
  if (!document.fullscreenElement) {
    // Attempt fullscreen after a small delay to allow navigation transition
    setTimeout(() => {
      document.documentElement.requestFullscreen?.().catch((error) => {
        console.error("Error requesting fullscreen", error);
      });
    }, 50);
  }
}
</script>

<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="py-4 bg-background d-flex align-center justify-center"
    @click="enterConsoleMode"
  >
    <div class="d-flex flex-column align-center">
      <v-icon :color="route.path.startsWith('/console') ? 'primary' : ''">
        mdi-television-play
      </v-icon>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{ 'text-primary': route.path.startsWith('/console') }"
        >
          Console
        </span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>
