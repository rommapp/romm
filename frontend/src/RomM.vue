<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "vue";
import { useTheme } from "vuetify";
import { useBrowserLocale } from "@/composables/useBrowserLocale";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";

// Lazy-loaded: RomM.vue is the first module main.ts evaluates, and the banner
// transitively imports the API layer (stores → services/api → router). A
// static import would pull that graph into bootstrap and trip the
// api-client ↔ router circular-import TDZ (see the theme notes below).
const BackendStatusBanner = defineAsyncComponent(
  () => import("@/v2/components/AppShell/BackendStatusBanner.vue"),
);

const vuetifyTheme = useTheme();
useBrowserLocale();

// Theme reads the raw localStorage ref: we stay off useUISettings here because
// it imports the API layer and would trigger an API-client ↔ router circular-
// import TDZ during bootstrap (RomM.vue is the first module main.ts loads).
const themeSetting = useUserLocalStorage<"auto" | "dark" | "light">(
  "settings.theme",
  "dark",
);

// Centralized theme resolution: Vuetify only knows the "dark" / "light"
// pair. The app's own colour story is driven by tokens on the .r-v2-*
// classes below, not by Vuetify's runtime theme.
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

const activeThemeName = computed<"dark" | "light">(() =>
  prefersDark.value ? "dark" : "light",
);

watch(
  activeThemeName,
  (name) => {
    if (vuetifyTheme.global.name.value !== name) {
      void vuetifyTheme.change(name);
    }
  },
  { immediate: true },
);

// Apply the token scope to <html>. Vuetify teleports overlays (VDialog,
// VMenu) into `<body> > .v-overlay-container`, which sits OUTSIDE both the
// AppLayout `.r-v2` wrapper AND <v-app>. Putting the classes on <html> means
// the entire document inherits the CSS custom properties so
// `var(--r-color-...)` resolves inside any teleported dialog/menu.
watch(
  prefersDark,
  (dark) => {
    const root = document.documentElement;
    root.classList.add("r-v2");
    root.classList.toggle("r-v2-dark", dark);
    root.classList.toggle("r-v2-light", !dark);
  },
  { immediate: true },
);
</script>

<template>
  <v-app id="application">
    <v-main id="main" class="no-transition" tag="div">
      <router-view />
    </v-main>
    <!-- Backend reachability strip. Mounted at the root so it covers both the
         auth layout (login/setup) and the main shell, and owns the app-wide
         connection poll + auto-recovery. -->
    <BackendStatusBanner />
  </v-app>
</template>

<style scoped>
#main.no-transition {
  transition: none;
}
</style>
