<script setup lang="ts">
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
      <v-icon :color="$route.path.startsWith('/console') ? 'primary' : ''">
        mdi-television-play
      </v-icon>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{ 'text-primary': $route.path.startsWith('/console') }"
        >
          Play
        </span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>

<script lang="ts">
export default {
  methods: {
    async enterConsoleMode() {
      try {
        // navigate first so route guards run promptly
        this.$router.push({ name: "console-home" });
        const docEl = document.documentElement as HTMLElement & {
          requestFullscreen?: () => Promise<void>;
        };
        if (!document.fullscreenElement && docEl.requestFullscreen) {
          // Attempt fullscreen after a small delay to allow navigation transition
          setTimeout(() => {
            docEl.requestFullscreen?.().catch(() => {
              /* ignore */
            });
          }, 50);
        }
      } catch {
        /* swallow */
      }
    },
  },
};
</script>
