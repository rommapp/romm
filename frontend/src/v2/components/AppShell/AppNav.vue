<script setup lang="ts">
// AppNav — the top navigation. Logo on the left, centred tab pill of
// content destinations (Home / Platforms / Collections / Search), and
// a right cluster of utility chrome (scanning indicator, user menu).
// Highlighting is derived from `route.path`
// rather than route names so gallery subroutes (e.g. /rom/:id) still
// light up the Home tab.
//
// Library tools (Scan / Upload) are administrative actions, not content
// destinations — they live in the user menu's Library group, keeping the
// primary nav focused on browsing destinations.
import { RSliderBtnGroup, RImg } from "@v2/lib";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import ScanningIndicator from "@/v2/components/AppShell/ScanningIndicator.vue";
import UserMenu from "@/v2/components/AppShell/UserMenu.vue";
import { useNavDestinations } from "@/v2/composables/useNavDestinations";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

// Primary destinations + active-tab logic shared with BottomNav.
const { destinations: tabs, activeId: activeTab } = useNavDestinations();

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
</script>

<template>
  <header class="r-v2-nav-bar" :class="{ 'r-v2-nav-bar--scrolled': scrolled }">
    <nav class="r-v2-nav">
      <router-link to="/" class="r-v2-nav__logo" :aria-label="t('common.home')">
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
          :aria-label="t('common.primary-navigation')"
        />
      </div>

      <div class="r-v2-nav__right">
        <ScanningIndicator />
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

/* Reduced-motion / low-power: the glass is a backdrop-filter blur, which is
   expensive on weak GPUs and, against the now-solid page background (the
   backdrop art is dropped in this mode), just reads as murky. Swap it for a
   flat opaque surface so the fixed bar stays a clean, solid strip as content
   scrolls under it. */
:global(html.r-v2-reduced-motion) .r-v2-nav-bar::before {
  background: var(--r-color-bg);
  backdrop-filter: none;
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
  justify-self: start;
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

/* On sm-and-down (phones + small tablets / landscape, <960px) the four
   primary destinations move to the bottom tab bar (BottomNav), so the
   centre pill is dropped from the top nav and the bar keeps only the
   logo (far left) + user cluster (far right). With just those two
   children, collapse to a 2-column grid so the cluster tracks the right
   edge — the default `1fr auto 1fr` would auto-place it into the now-
   empty centre column instead of the trailing one. The gutter follows
   `--r-row-pad` (20px sm, 14px xs) so logo + user line up with the Home
   sections' content edge. */
html[data-bp~="sm-and-down"] .r-v2-nav {
  grid-template-columns: 1fr auto;
}
html[data-bp~="sm-and-down"] .r-v2-nav__center {
  display: none;
}

/* The wordmark stays on the tablet range but drops on the tightest
   phones so the isotipo + user cluster have room. */
html[data-bp~="xs"] .r-v2-nav__logo-word {
  display: none;
}
</style>
