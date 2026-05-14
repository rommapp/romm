<script setup lang="ts">
// GameCard — portrait game cover with hover overlay.
//
// Feature composite (not a lib primitive): depends on SimpleRom,
// useGameActions (via GameActionBtn), useBackgroundArt, and the store
// layer. Lives under `components/` instead of `lib/` for
// that reason — the library is reserved for truly generic primitives
// that a Storybook reader can drop into a page without wiring stores or
// a router.
//
// Shape adapted from the artist mockup:
//   * 158×213 card art, 8px radius
//   * Rating badge top-right (appear on hover)
//   * Platform icon (TR, always visible): semi-transparent circle with the
//     platform's icon — toggle via `showPlatformIcon`.
//   * Hover overlay: play (center) · action row (BL: download, collection,
//     favorite, more) — action buttons are the shared GameActionBtn atom
//     so the card and the GameDetails header stay visually + behaviourally
//     in sync.
//   * Label below the card, 11.5px, truncated
//   * Optional `hero` variant: 300×169 (16:9) + larger multi-line label
//
// Static mode (`static`) strips the gallery chrome — no router-link,
// no action overlay, no rating / status / platform-icon badges, no
// background-art highlight on hover. Click emits `@click` instead of
// navigating. Hover scale stays by default (suppress with `noHover` for
// purely-decorative surfaces like the edit-dialog cover preview) and
// the view-transition reverse-paint still wires for real roms.
// Synthetic roms (rom.id falsy) skip ALL view-transition wiring since
// they have no destination.
//
// Other static-friendly props:
//   * `coverSrc` overrides the cover URL chain — used for preview blobs
//     (edit dialog) and external provider URLs (match dialog).
//   * `showTitle` toggles the label below the cover — defaults true.
//   * `selected` paints a brand-coloured outline on the cover art for
//     pickers (match-flow source variants, multi-select galleries).
//   * `#overlay` slot renders content on top of the cover for badges
//     that aren't part of the default gallery overlay (e.g. metadata
//     provider logos in the match-flow source picker).
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useGameActions } from "@/v2/composables/useGameActions";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";
import RPlatformIcon from "@/v2/lib/media/RPlatformIcon/RPlatformIcon.vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  rom: SimpleRom;
  to?: string;
  hero?: boolean;
  focused?: boolean;
  webp?: boolean;
  showPlatformIcon?: boolean;
  /** Passive mode — root is `<article role="button">` instead of a
   *  router-link; action overlay / rating / status / platform-icon /
   *  bg-art highlight are all suppressed. Click emits `@click` for the
   *  consumer to handle. Hover scale stays unless `noHover` is set. */
  static?: boolean;
  /** Suppress the hover scale + shadow. Use for purely-decorative
   *  surfaces (edit-dialog cover preview) where the card isn't an
   *  affordance. Only meaningful in `static` mode. */
  noHover?: boolean;
  /** Toggle the label below the cover. Defaults true to match the
   *  gallery experience. */
  showTitle?: boolean;
  /** Override the resolved cover URL. Used for local preview blobs
   *  (edit dialog) and external provider URLs (match dialog source
   *  variants). Bypasses the path/webp/url_cover chain. */
  coverSrc?: string | null;
  /** Paint a brand-coloured outline to mark the card as selected
   *  (cover-variant picker, multi-select gallery). */
  selected?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  to: undefined,
  showPlatformIcon: true,
  static: false,
  noHover: false,
  showTitle: true,
  coverSrc: undefined,
  selected: false,
});

const EXTENSION_REGEX = /\.(png|jpg|jpeg)$/i;

const imgError = ref(false);
const imgLoaded = ref(false);

const coverUrl = computed(() => {
  // Explicit override wins — consumer already resolved the URL
  // (preview blob, external provider URL, …). No webp rewrite here:
  // the caller's URL is treated as final.
  if (props.coverSrc != null) return props.coverSrc;
  const path = props.rom.path_cover_large ?? props.rom.path_cover_small ?? null;
  if (!path) return null;
  return props.webp ? path.replace(EXTENSION_REGEX, ".webp") : path;
});

// Synthetic roms (id = 0 / null / undefined) have no destination — skip
// the entire view-transition wiring so we never try to morph to a
// non-existent /rom/0 detail page.
const isSynthetic = computed(() => !props.rom.id);

const fallbackUrl = computed(() => props.rom.url_cover ?? null);
const showFallback = computed(() => imgError.value && !!fallbackUrl.value);

const title = computed(() => props.rom.name || props.rom.fs_name_no_ext);
const platformShort = computed(
  () => props.rom.platform_custom_name || props.rom.platform_display_name,
);

const href = computed(() => props.to ?? `/rom/${props.rom.id}`);

const setBgArt = useBackgroundArt();
// Same handler fires on hover AND focus so keyboard/gamepad users get
// the background cross-fade to the focused cover — mirrors what mouse
// users see when they rest a pointer on the card. Suppressed in static
// mode (the card isn't part of a gallery surface where the background
// reads as the focused cover).
function onHighlight() {
  if (props.static) return;
  if (coverUrl.value) setBgArt(coverUrl.value);
  else if (fallbackUrl.value) setBgArt(fallbackUrl.value);
}

const ratingLabel = computed(() => {
  const r = props.rom.rom_user?.rating;
  return r && r > 0 ? r.toString() : null;
});

// Shared-element morph: when the user clicks through to GameDetails, tag
// the card art so the browser pairs it with the destination cover and
// animates between them. Modifier keys / middle-click fall through to
// the regular router-link behaviour so opening in a new tab still works.
const router = useRouter();
const artEl = ref<HTMLElement | null>(null);
const { morphTransition } = useViewTransition();
const actions = useGameActions(() => props.rom);

// Stop propagation so the card's morph + router push doesn't fire when
// the user actually wanted to jump to the platform gallery.
function onPlatformClick(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  actions.goToPlatform();
}

const emit = defineEmits<{
  (e: "click", event: MouseEvent): void;
}>();

function onCardClick(e: MouseEvent) {
  // Static mode: consumer owns the click. No router push, no forward
  // morph — just hand the event off.
  if (props.static) {
    emit("click", e);
    return;
  }
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  if (!artEl.value) return;
  e.preventDefault();
  morphTransition(
    { el: artEl.value, name: `rom-cover-${props.rom.id}` },
    async () => {
      await router.push(href.value);
    },
  );
}

function onStaticKeydown(e: KeyboardEvent) {
  // Enter / Space activate the card when it's rendered as a plain
  // <article role="button"> instead of a router-link.
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    emit("click", e as unknown as MouseEvent);
  }
}

// Reverse-morph tag: when GameDetails is leaving (BackBtn / navbar /
// browser back), `pendingMorphName` is set and we paint the matching
// view-transition-name on the destination card so the browser can pair
// it with the GameDetails cover. Synthetic roms (no real id) skip
// this entirely — they can't be a morph destination.
const morphStyle = computed(() => {
  if (isSynthetic.value) return undefined;
  const name = `rom-cover-${props.rom.id}`;
  return pendingMorphName.value === name
    ? { viewTransitionName: name }
    : undefined;
});
</script>

<template>
  <component
    :is="static ? 'article' : 'router-link'"
    :to="static ? undefined : href"
    :role="static ? 'button' : undefined"
    :tabindex="static ? 0 : undefined"
    class="r-gc"
    :class="{
      'r-gc--hero': hero,
      'r-gc--focused': focused,
      'r-gc--static': static,
      'r-gc--no-hover': noHover,
      'r-gc--selected': selected,
    }"
    :aria-label="title"
    :aria-pressed="static ? selected : undefined"
    :data-rom-id="rom.id"
    @click="onCardClick"
    @keydown="static ? onStaticKeydown($event) : undefined"
    @mouseenter="onHighlight"
    @focus="onHighlight"
  >
    <div ref="artEl" class="r-gc__art" :style="morphStyle">
      <img
        v-if="(coverUrl || fallbackUrl) && !(imgError && !fallbackUrl)"
        :src="
          showFallback ? (fallbackUrl ?? undefined) : (coverUrl ?? undefined)
        "
        :alt="title"
        loading="lazy"
        decoding="async"
        @load="imgLoaded = true"
        @error="imgError = true"
      />
      <div v-else class="r-gc__placeholder">
        {{ title }}
      </div>

      <!-- Consumer-driven overlay slot — sits above the cover, below
           the gallery chrome. Use for badges that aren't part of the
           default overlay set (provider logos, custom status pills). -->
      <div v-if="$slots.overlay" class="r-gc__overlay-slot">
        <slot name="overlay" />
      </div>

      <!-- Gallery chrome — all suppressed in static mode. -->
      <template v-if="!static">
        <div v-if="ratingLabel" class="r-gc__rating">★ {{ ratingLabel }}</div>

        <RBtn
          v-if="showPlatformIcon"
          icon
          size="x-small"
          variant="text"
          class="r-gc__platform-icon"
          :aria-label="`Browse ${platformShort}`"
          @click="onPlatformClick"
        >
          <RPlatformIcon
            :slug="rom.platform_slug"
            :fs-slug="rom.platform_fs_slug"
            :alt="platformShort"
            :size="18"
          />
        </RBtn>

        <GameActionBtn
          :rom="rom"
          action="status"
          size="small"
          orientation="vertical"
        />

        <!-- Hover overlay — action buttons are the shared GameActionBtn. -->
        <div class="r-gc__overlay">
          <div class="r-gc__overlay-center">
            <GameActionBtn :rom="rom" action="play" variant="emphasized" />
          </div>

          <div class="r-gc__overlay-bottom">
            <GameActionBtn :rom="rom" action="download" size="small" />
            <GameActionBtn :rom="rom" action="collection" size="small" />
            <GameActionBtn :rom="rom" action="favorite" size="small" />
            <GameActionBtn :rom="rom" action="more" size="small" />
          </div>
        </div>
      </template>
    </div>
    <div v-if="showTitle" class="r-gc__label">
      {{ title }}
    </div>
  </component>
</template>

<style scoped>
.r-gc {
  flex-shrink: 0;
  cursor: pointer;
  position: relative;
  outline: none;
  width: var(--r-card-art-w);
  text-decoration: none;
  color: var(--r-color-fg);
}

.r-gc__art {
  width: var(--r-card-art-w);
  height: var(--r-card-art-h);
  border-radius: var(--r-radius-art);
  overflow: hidden;
  position: relative;
  background: var(--r-color-cover-placeholder);
  outline: 2.5px solid transparent;
  outline-offset: 3px;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.r-gc__art img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.r-gc__placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  text-align: center;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.4;
  color: var(--r-color-fg-muted);
}

/* ── Hover overlay ─────────────────────────────────────────── */
.r-gc__overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, black 45%, transparent) 0%,
    color-mix(in srgb, black 10%, transparent) 35%,
    color-mix(in srgb, black 10%, transparent) 55%,
    color-mix(in srgb, black 60%, transparent) 100%
  );
  opacity: 0;
  transition: opacity 0.12s ease;
  display: flex;
  flex-direction: column;
  padding: 8px;
  border-radius: var(--r-radius-art);
}

.r-gc__overlay-center {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}
.r-gc__overlay-bottom {
  display: flex;
  justify-content: space-around;
  align-items: center;
}

/* Top-right always-visible platform icon. Sits on the cover (outside the
   hover overlay) so it stays readable at rest. Click navigates to the
   platform gallery; tooltip shows the full platform name.
   `z-index` keeps the button above `.r-gc__overlay`, which would
   otherwise eat clicks because it covers the full art via `inset: 0`. */
.r-gc__platform-icon {
  position: absolute !important;
  top: 7px;
  right: 7px;
  z-index: 2;
  width: 28px !important;
  height: 28px !important;
  min-width: 28px !important;
  min-height: 28px !important;
  border-radius: 50% !important;
  background: var(--r-color-overlay-scrim-strong) !important;
  border: 1px solid var(--r-color-overlay-border) !important;
  color: var(--r-color-overlay-fg) !important;
  /* Override RBtn's at-rest opacity (0.7) so the 78% scrim reads at
     full strength — without this the bg modulates down to ~55% and
     reads faint over busy cover art. */
  opacity: 1 !important;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    transform 0.12s ease;
}
.r-gc__platform-icon:hover {
  background: color-mix(in srgb, black 90%, transparent) !important;
  border-color: var(--r-color-overlay-border-strong) !important;
  transform: scale(1.08);
}

/* Platform badge */
.r-gc__badge {
  position: absolute;
  bottom: 7px;
  left: 7px;
  background: var(--r-color-overlay-scrim-strong);
  border: 1px solid var(--r-color-overlay-border);
  border-radius: var(--r-radius-sm);
  padding: 2px 6px;
  font-size: 9.5px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.03em;
  color: var(--r-color-overlay-fg-secondary);
  opacity: 0;
  transition: opacity 0.12s ease;
  max-width: calc(100% - 14px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-gc__rating {
  position: absolute;
  top: 11px;
  left: 50%;
  transform: translateX(-50%);
  background: color-mix(in srgb, black 78%, transparent);
  border: 1px solid var(--r-color-romm-gold);
  border-radius: var(--r-radius-sm);
  padding: 2px 6px;
  font-size: 9.5px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-romm-gold);
  opacity: 0;
  transition: opacity 0.12s ease;
}

.r-gc:hover .r-gc__art,
.r-gc:focus-visible .r-gc__art,
.r-gc--focused .r-gc__art {
  transform: scale(1.05);
  box-shadow: var(--r-elev-3);
}

/* `noHover` suppresses the scale + shadow for purely-decorative
   surfaces (edit-dialog cover preview). Keyboard focus still paints
   the brand outline so the card remains reachable. */
.r-gc--no-hover {
  cursor: default;
}
.r-gc--no-hover:hover .r-gc__art,
.r-gc--no-hover:focus-visible .r-gc__art {
  transform: none;
  box-shadow: none;
}
.r-gc:hover .r-gc__overlay,
.r-gc:focus-visible .r-gc__overlay,
.r-gc--focused .r-gc__overlay {
  opacity: 1;
}

/* Consumer-driven `#overlay` slot — top-right anchor by default so
   provider logos / status pills sit out of the way of the rating
   centred above. `pointer-events: none` lets clicks pass through to
   the card so the consumer doesn't have to opt out per-element. */
.r-gc__overlay-slot {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 4px;
  pointer-events: none;
}
.r-gc:hover .r-gc__badge,
.r-gc:focus-visible .r-gc__badge,
.r-gc--focused .r-gc__badge,
.r-gc:hover .r-gc__rating,
.r-gc:focus-visible .r-gc__rating,
.r-gc--focused .r-gc__rating {
  opacity: 1;
}

/* Status badge — pinned to the cover's top-left corner, mirror of the
   platform icon on the right. The actual <button> lives inside
   GameActionBtn's RMenu activator slot, so we reach it via `:deep`
   matching the action class. Visibility:
   - status set     → always visible (`--active-status`)
   - status not set → invisible by default; fades in on card hover. */
.r-gc :deep(.r-v2-game-btn--action-status) {
  position: absolute;
  top: 7px;
  left: 7px;
  z-index: 2;
  opacity: 0;
}
.r-gc:hover :deep(.r-v2-game-btn--action-status),
.r-gc:focus-visible :deep(.r-v2-game-btn--action-status),
.r-gc--focused :deep(.r-v2-game-btn--action-status),
.r-gc :deep(.r-v2-game-btn--active-status) {
  opacity: 1;
}

/* Keyboard / gamepad focus — paint the outline in the brand colour and
   stack a drop-shadow + outer bloom on top so the focused card reads
   distinctly from hover. Mirrors the v1 console GameCard pattern. */
.r-gc:focus-visible {
  outline: none;
}
.r-gc:focus-visible .r-gc__art {
  outline-color: var(--r-color-brand-primary);
  box-shadow:
    0 8px 28px color-mix(in srgb, black 40%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent);
}

/* `selected` — same brand-outline language as focus, but persistent.
   Used by cover-variant pickers and multi-select galleries to mark the
   currently-picked card without relying on focus state. */
.r-gc--selected .r-gc__art {
  outline-color: var(--r-color-brand-primary);
  box-shadow:
    0 8px 28px color-mix(in srgb, black 40%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 50%, transparent);
}

.r-gc__label {
  margin-top: 7px;
  font-size: 11.5px;
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.18s;
  padding: 0 1px;
  text-align: center;
}
.r-gc:hover .r-gc__label,
.r-gc:focus-visible .r-gc__label,
.r-gc--focused .r-gc__label {
  color: var(--r-color-fg);
}

/* ── Hero (16:9) variant ──────────────────────────────────── */
.r-gc--hero {
  width: var(--r-hero-w);
}
.r-gc--hero .r-gc__art {
  width: var(--r-hero-w);
  height: var(--r-hero-h);
  border-radius: var(--r-radius-lg);
}
.r-gc--hero .r-gc__overlay {
  border-radius: var(--r-radius-lg);
}
.r-gc--hero .r-gc__label {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  max-width: var(--r-hero-w);
  white-space: normal;
  text-align: center;
  text-overflow: unset;
}

/* Mobile */
@media (max-width: 768px) {
  .r-gc {
    width: 130px;
  }
  .r-gc__art {
    width: 130px;
    height: 175px;
  }
  .r-gc--hero {
    width: 220px;
  }
  .r-gc--hero .r-gc__art {
    width: 220px;
    height: 124px;
  }
  .r-gc__label {
    font-size: 11px;
  }
  /* Actions always visible on touch (no hover) */
  .r-gc__overlay-bottom {
    opacity: 1;
  }
}
</style>
