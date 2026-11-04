<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "vue";
import { useBrowserLocale } from "@/composables/useBrowserLocale";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";

// Lazy-loaded: RomM.vue is the first module main.ts evaluates, and the banner
// transitively imports the API layer (stores → services/api → router). A
// static import would pull that graph into bootstrap and trip the
// api-client ↔ router circular-import TDZ (see the theme notes below).
const BackendStatusBanner = defineAsyncComponent(
  () => import("@/components/AppShell/BackendStatusBanner.vue"),
);

useBrowserLocale();

// Theme reads the raw localStorage ref: we stay off useUISettings here because
// it imports the API layer and would trigger an API-client ↔ router circular-
// import TDZ during bootstrap (RomM.vue is the first module main.ts loads).
const themeSetting = useUserLocalStorage<"auto" | "dark" | "light">(
  "settings.theme",
  "dark",
);

// Centralized theme resolution: the colour story is driven by tokens on the
// .r-* classes below.
const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
const systemPrefersDark = ref(mediaMatch.matches);

function handleSystemThemeChange(event: MediaQueryListEvent) {
  systemPrefersDark.value = event.matches;
}

onMounted(() => {
  mediaMatch.addEventListener("change", handleSystemThemeChange);
});

onUnmounted(() => {
  mediaMatch.removeEventListener("change", handleSystemThemeChange);
});

const prefersDark = computed(
  () =>
    themeSetting.value === "dark" ||
    (themeSetting.value === "auto" && systemPrefersDark.value),
);

// Overlays (RDialog, RMenu, RTooltip) teleport outside the app root, so the
// theme classes live on <html> for `var(--r-color-...)` to resolve there.
watch(
  prefersDark,
  (dark) => {
    const root = document.documentElement;
    root.classList.add("r-app");
    root.classList.toggle("r-dark", dark);
    root.classList.toggle("r-light", !dark);
  },
  { immediate: true },
);
</script>

<template>
  <div id="application">
    <div class="r-app-wrap">
      <div id="main">
        <router-view />
      </div>
      <!-- Backend reachability strip. Mounted at the root so it covers both the
           auth layout (login/setup) and the main shell, and owns the app-wide
           connection poll + auto-recovery. -->
      <BackendStatusBanner />
    </div>
  </div>
</template>

<style scoped>
#application {
  display: flex;
}

.r-app-wrap {
  display: flex;
  flex: auto;
  flex-direction: column;
  position: relative;
  max-width: 100%;
  min-height: 100dvh;
  backface-visibility: hidden;
}

#main {
  flex: 1 0 auto;
  max-width: 100%;
}
</style>
