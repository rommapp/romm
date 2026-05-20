<script setup lang="ts">
// AppNav — the top navigation. Logo on the left, centred tab pill,
// "switch to classic UI" icon + user menu on the right. Highlighting
// is derived from `route.path` rather than route names so gallery
// subroutes (e.g. /rom/:id) still light up the Home tab.
import { RBtn, RIcon, RSliderBtnGroup, RTooltip, RImg } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useUiVersion } from "@/composables/useUiVersion";
import storeAuth from "@/stores/auth";
import UserMenu from "@/v2/components/AppShell/UserMenu.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const route = useRoute();
const uiVersion = useUiVersion();
const { scopes } = storeToRefs(storeAuth());

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

type TabId = "home" | "platforms" | "collections" | "search" | "tools";
// `icon` ships on every tab so the xs breakpoint can drop the label
// and the pill collapses to icon-only without changing markup.
// `to` for `tools` lands on Scan by default — the in-view tab picker
// then handles lateral switching to Upload / Patcher.
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
  {
    id: "tools" as const,
    label: "Library Tools",
    ariaLabel: "Library Tools",
    icon: "mdi-tools",
    to: "/scan",
  },
];

const activeTab = computed<TabId | null>(() => {
  const path = route.path;
  if (path === "/") return "home";
  if (path.startsWith("/platform")) return "platforms";
  if (path.startsWith("/collection")) return "collections";
  if (path.startsWith("/search")) return "search";
  // Library Tools group — Scan / Upload / Patcher all light up the
  // same tab. They're not under a shared `/tools/*` URL prefix
  // (URLs stayed flat after the layout refactor) so we match each
  // path explicitly.
  if (path === "/scan" || path === "/upload" || path === "/patcher") {
    return "tools";
  }
  return null;
});

// Library Tools sub-pill — appears below the navbar when the Tools
// tab is active, with the same aesthetic as the top pill. Replaces
// the old in-layout picker. The chevron on the Tools tab rotates to
// mirror the open state. We keep the open state route-derived (no
// manual toggle) so the chevron + sub-pill always agree with where
// the user is — the secondary controls don't need their own UI state
// machine. Permission checks mirror the previous layout picker so
// users without write scope see the sub-tools as disabled chips.
const canScan = computed(() => scopes.value.includes("platforms.write"));
const canUpload = computed(() => scopes.value.includes("roms.write"));

type SubToolId = "scan" | "upload" | "patcher";

const subTools = computed(() => [
  {
    id: "scan" as const,
    label: t("scan.scan"),
    ariaLabel: t("scan.scan"),
    icon: "mdi-magnify-scan",
    to: "/scan",
    disabled: !canScan.value,
  },
  {
    id: "upload" as const,
    label: t("common.upload-roms", "Upload ROMs"),
    ariaLabel: t("common.upload-roms", "Upload ROMs"),
    icon: "mdi-cloud-upload-outline",
    to: "/upload",
    disabled: !canUpload.value,
  },
  {
    id: "patcher" as const,
    label: t("common.patcher"),
    ariaLabel: t("common.patcher"),
    icon: "mdi-file-cog-outline",
    to: "/patcher",
    disabled: false,
  },
]);

const activeSubTool = computed<SubToolId | null>(() => {
  if (route.path === "/scan") return "scan";
  if (route.path === "/upload") return "upload";
  if (route.path === "/patcher") return "patcher";
  return null;
});

const submenuOpen = computed(() => activeTab.value === "tools");
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
        >
          <!-- Default content for every item, plus a chevron on the
               Tools tab that rotates when the sub-pill is open. The
               chevron is decorative — interactivity stays on the tab
               (clicking the tab routes to /scan, which in turn flips
               activeTab→tools, which opens the sub-pill). -->
          <template #item="{ item }">
            <RIcon v-if="item.icon" :icon="item.icon" size="16" />
            <span v-if="item.label" class="r-slider-btn-group__label">
              {{ item.label }}
            </span>
            <RIcon
              v-if="item.id === 'tools'"
              icon="mdi-chevron-down"
              size="14"
              class="r-v2-nav__chevron"
              :class="{ 'r-v2-nav__chevron--open': submenuOpen }"
              aria-hidden="true"
            />
          </template>
        </RSliderBtnGroup>
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

    <!-- Library Tools sub-pill. Hangs from the bottom edge of the
         fixed header so it doesn't push page content. Centred via
         flex on the wrapper. The Transition produces a slide-down +
         fade-in with the `easeBack` overshoot so the pill snaps in
         with a touch of bounce. Symmetric (faster, no overshoot)
         leave so dismissals don't linger. `pointer-events:none` on
         the wrapper lets clicks pass through to whatever is below
         the navbar when the pill misses, while the pill itself
         re-enables them. -->
    <Transition name="r-v2-nav-sub" appear>
      <div v-if="submenuOpen" class="r-v2-nav__sub">
        <RSliderBtnGroup
          :model-value="activeSubTool"
          :items="subTools"
          variant="tab"
          :aria-label="t('library-tools.picker-aria', 'Library tools')"
          class="r-v2-nav__sub-pill"
        />
      </div>
    </Transition>
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

/* Grid `1fr auto 1fr` keeps the tab pill geometrically centred on the
   viewport regardless of the side clusters' widths. With flex +
   justify-content:center the pill drifts whenever logo and right
   cluster differ in size (which they always do). The 1fr side
   columns absorb the imbalance so the middle column stays anchored
   at the viewport's true centre. */
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
  display: flex;
  justify-content: center;
  /* Middle grid cell — pill takes its natural width and sits at
     the geometric centre of the viewport. */
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

/* Chevron on the Tools tab. Rotates 180° when the sub-pill is open,
   so the tab "owns" the open/close affordance visually even though
   the actual toggle is route-derived. `easeBack` adds a tiny
   overshoot for the juicy feel. Margin-left keeps it tight to the
   label without breaking the gap rhythm of the slider group. */
.r-v2-nav__chevron {
  margin-left: 2px;
  transition: transform var(--r-motion-med) var(--r-motion-ease-back);
  will-change: transform;
}
.r-v2-nav__chevron--open {
  transform: rotate(180deg);
}

/* Sub-pill wrapper. Lives inside the fixed header so it inherits the
   same top: 0 reference; `position: absolute; top: 100%` hangs it
   right under the navbar without bumping its height. The wrapper
   spans full width and centres its child so the pill sits at the
   geometric centre of the viewport (same anchor as the top pill).
   z-index just under the navbar so any scroll-glass at the top
   covers it during enter/leave if needed. */
.r-v2-nav__sub {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  padding-top: 8px;
  pointer-events: none;
  z-index: 99;
}
.r-v2-nav__sub-pill {
  pointer-events: auto;
  /* The shadow gives the floating pill a touch of depth above the
     page content beneath it, matching the navbar's own glass card. */
  box-shadow: 0 8px 22px color-mix(in srgb, black 28%, transparent);
}

.r-v2-nav-sub-enter-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-back);
}
.r-v2-nav-sub-leave-active {
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-nav-sub-enter-from,
.r-v2-nav-sub-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.96);
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
/* xs sub-pill also goes icon-only so the row of three sub-tools
   stays compact and centred. */
html[data-bp~="xs"] .r-v2-nav__sub-pill :deep(.r-slider-btn-group__label) {
  display: none;
}
html[data-bp~="xs"] .r-v2-nav__sub-pill :deep(.r-slider-btn-group--tab) {
  padding: 3px;
}
html[data-bp~="xs"] .r-v2-nav__sub-pill :deep(.r-slider-btn-group__btn) {
  padding: 0 8px !important;
}
</style>
