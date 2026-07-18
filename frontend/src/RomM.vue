<script setup lang="ts">
import { useIdle, useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import {
  computed,
  defineAsyncComponent,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
import SoundtrackMiniPlayer from "@/components/common/SoundtrackMiniPlayer.vue";
import { useUiVersion } from "@/composables/useUiVersion";
import storeConsole from "@/stores/console";
import storeLanguage from "@/stores/language";

// Lazy-loaded: RomM.vue is the first module main.ts evaluates, and the banner
// transitively imports the API layer (stores → services/api → router). A
// static import would pull that graph into bootstrap and trip the
// api-client ↔ router circular-import TDZ (see the theme/scope notes below).
const BackendStatusBanner = defineAsyncComponent(
  () => import("@/v2/components/AppShell/BackendStatusBanner.vue"),
);

const { locale } = useI18n();
const languageStore = storeLanguage();
const consoleStore = storeConsole();
const vuetifyTheme = useTheme();
const { consoleMode } = storeToRefs(consoleStore);
const { languages } = storeToRefs(languageStore);
const storedLocale = useLocalStorage("settings.locale", "");
const selectedLanguage = ref(
  languages.value.find((lang) => lang.value === storedLocale.value) ||
    languageStore.detectBrowserLanguage(),
);
locale.value = selectedLanguage.value.value;
languageStore.setLanguage(selectedLanguage.value);

// NOTE: uiVersion uses a module-level singleton ref (useUiVersion) so a write
// from the settings page is the SAME ref RomM.vue reads, triggering a gate
// re-evaluation and an instant v1 ↔ v2 swap with no reload. Theme likewise
// reads the raw localStorage ref — we stay off useUISettings here because it
// imports the API layer and would trigger an API-client ↔ router circular-
// import TDZ during bootstrap (RomM.vue is the first module main.ts loads).
const uiVersion = useUiVersion();
const themeSetting = useLocalStorage<"auto" | "dark" | "light">(
  "settings.theme",
  "dark",
);

const { idle: mouseIdle } = useIdle(100, {
  events: ["mousemove", "mousedown", "wheel", "touchstart"],
});

// Centralized theme resolution — Vuetify only knows the "dark" / "light"
// pair (used by v1 surfaces and any remaining v1 components rendered
// inside v2). v2's own colour story is driven by tokens on the .r-v2-*
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
      vuetifyTheme.change(name);
    }
  },
  { immediate: true },
);

const isV2 = computed(() => uiVersion.value === "v2");

// Apply the v2 token scope to <html> when v2 is active. Vuetify teleports
// overlays (VDialog, VMenu) into `<body> > .v-overlay-container` — which
// sits OUTSIDE both the AppLayout `.r-v2` wrapper AND <v-app>. Putting the
// classes on <html> means the entire document inherits the v2 CSS custom
// properties so `var(--r-color-...)` resolves inside any teleported
// dialog/menu. v1 mode strips the classes, keeping v1 CSS unaffected.
watch(
  [isV2, prefersDark],
  ([v2, dark]) => {
    const root = document.documentElement;
    root.classList.toggle("r-v2", v2);
    root.classList.toggle("r-v2-dark", v2 && dark);
    root.classList.toggle("r-v2-light", v2 && !dark);
  },
  { immediate: true },
);
</script>

<template>
  <v-app id="application" :class="{ 'mouse-hidden': consoleMode && mouseIdle }">
    <v-main id="main" class="no-transition">
      <router-view v-if="!isV2" v-slot="{ Component }">
        <component :is="Component" />
        <!-- Fade out the app loading logo -->
        <Transition name="fade" mode="out-in">
          <div v-if="!Component" id="app-loading-logo">
            <img
              src="/assets/logos/romm_logo_xbox_one_circle_grayscale.svg"
              alt="Romm Logo"
            />
          </div>
        </Transition>
      </router-view>
      <router-view v-else name="v2" />
    </v-main>
    <!-- v2-only: backend reachability strip. Mounted at the root so it
         covers both the auth layout (login/setup) and the main shell, and
         owns the app-wide connection poll + auto-recovery. -->
    <BackendStatusBanner v-if="isV2" />
    <!-- v1 only: in v2 the soundtrack mini-player is mounted from
         the v2 AppLayout (`Soundtrack/MiniPlayer.vue`) so it can use
         v2 primitives + tokens. Two mini-players would race for the
         audio element. -->
    <SoundtrackMiniPlayer v-if="!isV2" />
  </v-app>
</template>

<style scoped>
#main.no-transition {
  transition: none;
}

#application.mouse-hidden,
#application.mouse-hidden * {
  cursor: none !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.35s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
