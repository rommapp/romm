<script setup lang="ts">
// AppNav — the top navigation. Logo on the left, centred tab pill,
// "switch to classic UI" icon + user menu on the right. Highlighting
// is derived from `route.path` rather than route names so gallery
// subroutes (e.g. /rom/:id) still light up the Home tab.
import { RBtn, RSliderBtnGroup, RTooltip, RImg } from "@v2/lib";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useUiVersion } from "@/composables/useUiVersion";
import UserMenu from "@/v2/components/AppShell/UserMenu.vue";

defineOptions({ inheritAttrs: false });

const route = useRoute();
const uiVersion = useUiVersion();

function switchToV1() {
  uiVersion.value = "v1";
}

// At the top of the page the navbar is fully transparent so the cover
// art / page bg shows through cleanly. Once the user scrolls, content
// would otherwise bleed visibly under the bar — we paint the glass
// surface (bg + blur) with a soft transition so the bar stays readable.
// Views that own their own internal scroll (Gallery, GameDetails) never
// move window.scrollY → the bar stays transparent there.
const scrolled = ref(false);
const SCROLL_THRESHOLD = 4;

function onScroll() {
  scrolled.value = window.scrollY > SCROLL_THRESHOLD;
}

onMounted(() => {
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", onScroll);
});

type TabId = "home" | "platforms" | "collections" | "search";
const tabs = [
  { id: "home" as const, label: "Home", to: "/" },
  { id: "platforms" as const, label: "Platforms", to: "/platforms" },
  { id: "collections" as const, label: "Collections", to: "/collections" },
  { id: "search" as const, label: "Search", to: "/search" },
];

const activeTab = computed<TabId | null>(() => {
  const path = route.path;
  if (path === "/") return "home";
  if (path.startsWith("/platform")) return "platforms";
  if (path.startsWith("/collection")) return "collections";
  if (path.startsWith("/search")) return "search";
  return null;
});
</script>

<template>
  <header class="r-v2-nav-bar" :class="{ 'r-v2-nav-bar--scrolled': scrolled }">
    <nav class="r-v2-nav">
      <router-link to="/" class="r-v2-nav__logo" aria-label="Home">
        <RImg
          src="/assets/isotipo.svg"
          alt="RomM isotipo"
          aria-hidden="true"
          class="r-v2-nav__logo-mark"
          :width="32"
        />
        <RImg
          src="/assets/logotipo.svg"
          alt="RomM logotipo"
          aria-hidden="true"
          class="r-v2-nav__logo-word"
          :width="70"
        />
      </router-link>

      <div class="r-v2-nav__center">
        <RSliderBtnGroup
          :model-value="activeTab"
          :items="tabs"
          variant="tab"
          aria-label="Primary navigation"
        />
      </div>

      <div class="r-v2-nav__right">
        <RTooltip text="Switch to classic UI" location="bottom">
          <template #activator="{ props: tooltipProps }">
            <RBtn
              v-bind="tooltipProps"
              prepend-icon="mdi-backup-restore"
              size="small"
              variant="text"
              class="r-v2-nav__classic"
              aria-label="Switch to classic UI"
              @click="switchToV1"
              >Classic UI</RBtn
            >
          </template>
        </RTooltip>

        <UserMenu />
      </div>
    </nav>
  </header>
</template>

<style scoped>
/* Fixed full-width strip. Transparent at rest so the page bg / cover
   art reads naturally; gains the glass surface (bg + blur + bottom
   border) once the user starts scrolling so content doesn't bleed
   through. The inner `<nav>` keeps its --r-page-max-w + margin auto
   so the nav content stays centred on ultrawide displays. */
.r-v2-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  height: var(--r-nav-h);
  background: transparent;
  border-bottom: 1px solid transparent;
  transition:
    background var(--r-motion-med) var(--r-motion-ease-out),
    backdrop-filter var(--r-motion-med) var(--r-motion-ease-out),
    -webkit-backdrop-filter var(--r-motion-med) var(--r-motion-ease-out),
    border-color var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-nav-bar--scrolled {
  background: color-mix(in srgb, var(--r-color-bg) 78%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom-color: var(--r-color-border);
}

.r-v2-nav {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  padding: 0 var(--r-row-pad);
  gap: 0;
}

.r-v2-nav__logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--r-color-fg);
  flex-shrink: 0;
  /* Both marks transition together so the glow reads as one gesture. */
  transition: filter var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-nav__logo:hover,
.r-v2-nav__logo:focus-visible {
  filter: drop-shadow(
    0 0 6px color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent)
  );
}
.r-v2-nav__logo:focus-visible {
  outline: none;
}

.r-v2-nav__logo-mark {
  width: 32px;
  height: 32px;
  display: block;
}

.r-v2-nav__logo-word {
  height: 22px;
  width: auto;
  display: block;
}

.r-v2-nav__center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.r-v2-nav__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* Ghost-pill styling for the "classic UI" button (matches the old RIconBtn
   ghost variant — translucent glass, subtle border). */
.r-v2-nav__classic {
  background: var(--r-color-surface) !important;
  border: 1px solid var(--r-color-border-strong) !important;
  color: var(--r-color-fg-secondary) !important;
  opacity: 1;
}
.r-v2-nav__classic:hover {
  background: var(--r-color-surface-hover) !important;
  color: var(--r-color-fg) !important;
}

html[data-bp~="xs"] .r-v2-nav {
  padding: 0 14px;
  justify-content: space-between;
}

html[data-bp~="xs"] .r-v2-nav__logo-word {
  display: none;
}

html[data-bp~="xs"] .r-v2-nav__center {
  display: none;
}
</style>
