<script setup lang="ts">
// AppNav — the top navigation. Logo on the left, centred tab pill of
// content destinations (Home / Platforms / Collections / Search), and
// a right cluster of utility chrome (scanning indicator, library tools
// dropdown, classic-UI escape hatch, user menu). Highlighting is
// derived from `route.path` rather than route names so gallery
// subroutes (e.g. /rom/:id) still light up the Home tab.
//
// Library tools used to live in this pill as a 5th tab with a vertical
// dropdown sub-pill. That conflated *administrative actions* with
// *content navigation*. The tools are now in the right cluster as a
// dedicated dropdown (LibraryToolsMenu), keeping the primary nav
// focused on browsing destinations.
import { RBtn, RSliderBtnGroup, RTooltip, RImg } from "@v2/lib";
import { onBeforeUnmount, onMounted, ref, computed } from "vue";
import { useRoute } from "vue-router";
import { useUiVersion } from "@/composables/useUiVersion";
import LibraryToolsMenu from "@/v2/components/AppShell/LibraryToolsMenu.vue";
import ScanningIndicator from "@/v2/components/AppShell/ScanningIndicator.vue";
import UserMenu from "@/v2/components/AppShell/UserMenu.vue";

defineOptions({ inheritAttrs: false });

const route = useRoute();
const uiVersion = useUiVersion();

function switchToV1() {
  uiVersion.value = "v1";
}

// At the top of the page the navbar is fully transparent so the page
// bg / cover art reads cleanly. Once the user scrolls, a `::before`
// pseudo-element fades in carrying the glass surface (bg + blur). The
// blur is **static** on the pseudo, with only `opacity` transitioning
// — transitioning `backdrop-filter` directly kept the blur layer alive
// and any hover repaint nearby would flash it.
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
// `icon` ships on every tab so the xs breakpoint can drop the label
// and the pill collapses to icon-only without changing markup.
// `ariaLabel` mirrors the visible label so the icon-only xs variant
// still names each link to screen readers / focus rings.
const tabs = [
  {
    id: "home" as const,
    label: "Home",
    ariaLabel: "Home",
    icon: "mdi-home-outline",
    to: "/",
  },
  {
    id: "platforms" as const,
    label: "Platforms",
    ariaLabel: "Platforms",
    icon: "mdi-controller",
    to: "/platforms",
  },
  {
    id: "collections" as const,
    label: "Collections",
    ariaLabel: "Collections",
    // Same glyph GameCard uses for its "add to collection" action —
    // keeps the icon stable across every generic "Collections"
    // surface so users learn it as the collections symbol.
    icon: "mdi-bookmark-outline",
    to: "/collections",
  },
  {
    id: "search" as const,
    label: "Search",
    ariaLabel: "Search",
    icon: "mdi-magnify",
    to: "/search",
  },
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
              icon="mdi-backup-restore"
              size="small"
              variant="text"
              class="r-v2-nav__classic"
              aria-label="Switch to classic UI"
              @click="switchToV1"
            ></RBtn>
          </template>
        </RTooltip>
        <ScanningIndicator />
        <LibraryToolsMenu />
        <UserMenu />
      </div>
    </nav>
  </header>
</template>

<style scoped>
/* Fixed full-width strip. Transparent at rest so the page bg / cover
   art reads naturally; gains the glass surface once the user scrolls.
   The glass (bg + blur) lives on a `::before` pseudo-element so we
   can transition only its **opacity** between scrolled / not-scrolled
   instead of transitioning `backdrop-filter` directly. Transitioning
   backdrop-filter is notoriously expensive — the browser keeps the
   blur layer "alive" the whole time and any nearby hover repaint
   invalidates it, producing a one-frame flicker. Static blur +
   opacity-only transition keeps the compositor layer stable. */
.r-v2-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  height: var(--r-nav-h);
  background: transparent;
  border-bottom: 1px solid transparent;
  transition: border-color var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-nav-bar::before {
  content: "";
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--r-color-bg) 78%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  opacity: 0;
  pointer-events: none;
  z-index: -1;
  transition: opacity var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-nav-bar--scrolled::before {
  opacity: 1;
}
.r-v2-nav-bar--scrolled {
  border-bottom-color: var(--r-color-border);
}

/* Grid `1fr auto 1fr` keeps the tab pill geometrically centred on the
   viewport regardless of the side clusters' widths. With flex +
   justify-content:center the pill drifts whenever logo and right
   cluster differ in size. The 1fr side columns absorb the imbalance
   so the middle column stays anchored at the viewport's true centre. */
.r-v2-nav {
  height: 100%;
  width: 100%;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
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
  display: flex;
  justify-content: center;
}

.r-v2-nav__right {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-self: end;
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
}

html[data-bp~="xs"] .r-v2-nav__logo-word {
  display: none;
}

/* xs collapses every primary tab to icon-only so the pill still fits
   between the logo and the right-side cluster. The labels live inside
   the RSliderBtnGroup's `r-slider-btn-group__label` span — we reach
   it via `:deep()` because the primitive is scoped. The router-link
   `aria-label` stays the source of accessible naming. */
html[data-bp~="xs"] .r-v2-nav__center :deep(.r-slider-btn-group__label) {
  display: none;
}
html[data-bp~="xs"] .r-v2-nav__center :deep(.r-slider-btn-group--tab) {
  padding: 3px;
}
html[data-bp~="xs"] .r-v2-nav__center :deep(.r-slider-btn-group__btn) {
  padding: 0 8px !important;
}
</style>
