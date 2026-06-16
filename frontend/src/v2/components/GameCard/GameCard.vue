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
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import SiblingBadge from "@/v2/components/GameCard/SiblingBadge.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useCoverArt } from "@/v2/composables/useCoverArt";
import { useGallerySelectionInput } from "@/v2/composables/useGallerySelectionInput";
import { useGameActions } from "@/v2/composables/useGameActions";
import { useViewTransition } from "@/v2/composables/useViewTransition";
import RCheckbox from "@/v2/lib/forms/RCheckbox/RCheckbox.vue";
import RPlatformIcon from "@/v2/lib/media/RPlatformIcon/RPlatformIcon.vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";
import storeGallerySelection from "@/v2/stores/gallerySelection";

defineOptions({ inheritAttrs: false });

interface Props {
  rom: SimpleRom;
  to?: string;
  hero?: boolean;
  /** Card scale tier. Drives the cover art width/height via the shared
   *  `--r-card-art-w/h` tokens, and the hero variant's `--r-hero-w/h`
   *  when `hero` is true.
   *    xs (48 × 64)   — list-row avatars
   *    sm (120 × 162) — dense pickers
   *    md (158 × 213) — gallery default (no class — keeps the global token)
   *    lg (200 × 270) — edit-dialog preview
   *    xl (240 × 324) — detail page cover
   *  Hero scales linearly with size (it's just an aspect-ratio change,
   *  not a separate scale), so `hero` + any `size` paints the 16:9
   *  shape at that tier's footprint. */
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  focused?: boolean;
  webp?: boolean;
  showPlatformIcon?: boolean;
  /** Passive mode — root is `<article role="button">` instead of a
   *  router-link; action overlay / rating / status / platform-icon /
   *  bg-art highlight are all suppressed. Click emits `@click` for the
   *  consumer to handle. Hover scale stays unless `noHover` is set. */
  static?: boolean;
  /** Fully decorative — root is a plain `<div>` with no role, no
   *  tabindex, no router wiring, no own click handlers. The whole
   *  card is visual content; the parent (typically an `<a>` or row
   *  button) owns interactivity and navigation. Avoids the nested-
   *  interactive HTML quirk when the card lives inside an anchor (eg.
   *  list-row avatars). Implies `static` semantics: no overlay /
   *  badges / bg highlight. */
  decorative?: boolean;
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
   *  (cover-variant picker, multi-select gallery). When `selectable`
   *  is true this prop is ignored — the card subscribes directly to
   *  `gallerySelection` so a single source of truth (the store)
   *  drives every selected card across the gallery. */
  selected?: boolean;
  /** Opt the card into the gallery's multi-select store. When true:
   *  the card reads its selected state from `gallerySelection`,
   *  shows a checkbox affordance (on hover or whenever the gallery
   *  is in selection mode), and routes its clicks through the
   *  selection-input composable (shift = range, ctrl/cmd = toggle,
   *  long-press on touch = enter mode). Defaults false so non-
   *  gallery consumers (pickers, edit-dialog previews) keep their
   *  prop-driven behaviour. */
  selectable?: boolean;
  /** Sparse position of the rom inside the gallery — the anchor that
   *  shift-range selection uses. Provided by `GalleryShell`. Required
   *  when `selectable` is true (the composable needs a position to
   *  store/restore the range anchor). */
  position?: number;
}

const props = withDefaults(defineProps<Props>(), {
  to: undefined,
  size: "md",
  showPlatformIcon: true,
  static: false,
  decorative: false,
  noHover: false,
  showTitle: true,
  coverSrc: undefined,
  selected: false,
  selectable: false,
  position: undefined,
});

// Cover resolution lives in `useCoverArt`, shared with the <GameCover>
// that actually renders the image / video / placeholder / spin in the
// template. The card keeps it only for: the background-art highlight
// (onHighlight), the `--r-cover-ratio` that sizes the art box, and the
// alt-art class that drops the card frame for a floating disc/cartridge.
const art = useCoverArt(() => props.rom, {
  coverSrc: () => props.coverSrc,
  webp: () => props.webp,
});
const coverUrl = art.coverUrl;
const fallbackUrl = art.fallbackUrl;
const coverAspectRatio = art.ratio;
// Alt-art styles (box3d / physical / miximage) drop the card frame so the
// artwork floats — but only while a real image renders; with no cover the
// placeholder keeps its grey box so the title stays readable.
const isAltStyle = computed(
  () =>
    art.style.value !== "cover_path" && !!(coverUrl.value || fallbackUrl.value),
);
// Forward view-transition morph targets the GameCover's box element.
const coverRef = ref<InstanceType<typeof GameCover> | null>(null);

// Synthetic roms (id = 0 / null / undefined) have no destination — skip
// the entire view-transition wiring so we never try to morph to a
// non-existent /rom/0 detail page.
const isSynthetic = computed(() => !props.rom.id);

const { t } = useI18n();
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
  if (props.static || props.decorative) return;
  if (coverUrl.value) setBgArt(coverUrl.value);
  else if (fallbackUrl.value) setBgArt(fallbackUrl.value);
}

// ── Cover hover / focus ─────────────────────────────────────────────
// Hover (mouse/touch) and focus (keyboard/gamepad) both mark the cover
// "active", which GameCover turns into disc spin / cartridge slot-in /
// hover video. `props.focused` is the gallery's gamepad-driven highlight.
const pointerInside = ref(false);
const keyboardFocused = ref(false);
const coverActive = computed(
  () =>
    !props.decorative &&
    (pointerInside.value || keyboardFocused.value || !!props.focused),
);

function onCoverEnter() {
  pointerInside.value = true;
  onHighlight();
}
function onCoverLeave() {
  pointerInside.value = false;
}
function onCoverFocus() {
  keyboardFocused.value = true;
  onHighlight();
}
function onCoverBlur() {
  keyboardFocused.value = false;
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

// Gallery selection — only wired when the consumer opts in via
// `selectable`. Outside the gallery (pickers, previews) the store
// stays untouched so a stray match-dialog selection can't leak into
// the gallery's selection bar.
const selectionStore = storeGallerySelection();
const selectionInput = useGallerySelectionInput();

const isSelected = computed(() =>
  props.selectable ? selectionStore.isSelected(props.rom.id) : props.selected,
);
/** True when the card should paint its checkbox affordance: any time
 *  the gallery is in selection mode (every card shows the checkbox so
 *  the user can see what is selected at a glance), or on hover when
 *  selection is idle (discoverability of the multi-select feature). */
const showCheckbox = computed(
  () =>
    props.selectable &&
    !props.static &&
    !props.decorative &&
    !isSynthetic.value,
);
const checkboxAlwaysOn = computed(
  () => props.selectable && !props.decorative && selectionStore.enabled,
);

function onCheckboxClick(e: MouseEvent) {
  // The checkbox itself is a deliberate selection gesture. We bind
  // RCheckbox in "controlled" mode (only `:model-value` — no v-model),
  // so the native input change is purely visual; `preventDefault`
  // here cancels the label → input click default so the input never
  // toggles itself, and our store mutation drives the next render.
  e.preventDefault();
  e.stopPropagation();
  if (props.position == null) return;
  if (e.shiftKey) {
    selectionInput.handleActivate(props.rom, props.position, e);
    return;
  }
  selectionStore.toggle(props.rom, props.position);
}

/** Capture-phase suppressor — when the gallery is in selectable mode
 *  AND the user is holding a modifier key, any click on the card
 *  (overlay buttons included: download / favorite / play / more /
 *  platform icon) is reinterpreted as a selection gesture. Without
 *  this, shift-clicking the favourite star would toggle the favourite
 *  AND extend the selection range — confusing. */
function onCardClickCapture(e: MouseEvent) {
  if (!props.selectable) return;
  if (!(e.shiftKey || e.ctrlKey || e.metaKey)) return;
  e.preventDefault();
  e.stopPropagation();
  if (props.position == null) return;
  selectionInput.handleActivate(props.rom, props.position, e);
}

function onCardClick(e: MouseEvent) {
  // Decorative mode: the card has no behaviour of its own. Let the
  // event bubble untouched so the parent (typically an anchor or row
  // button) handles navigation / selection — no emit, no morph.
  if (props.decorative) return;
  // Static mode: consumer owns the click. No router push, no forward
  // morph — just hand the event off.
  if (props.static) {
    emit("click", e);
    return;
  }

  // Gallery selection takes precedence over navigation when the card
  // opts in. Returns `true` if the click was consumed (mode active,
  // modifier pressed, long-press just fired); we short-circuit and
  // skip the morph + router push.
  if (
    props.selectable &&
    props.position != null &&
    selectionInput.handleActivate(props.rom, props.position, e)
  ) {
    return;
  }

  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  const el = coverRef.value?.el();
  if (!el) return;
  e.preventDefault();
  morphTransition({ el, name: `rom-cover-${props.rom.id}` }, async () => {
    await router.push(href.value);
  });
}

function onCardPointerDown(e: PointerEvent) {
  if (!props.selectable || props.position == null) return;
  selectionInput.handlePointerDown(props.rom, props.position, e);
}
function onCardPointerMove(e: PointerEvent) {
  if (!props.selectable) return;
  selectionInput.handlePointerMove(e);
}
function onCardPointerEnd() {
  if (!props.selectable) return;
  selectionInput.handlePointerEnd();
}

function onStaticKeydown(e: KeyboardEvent) {
  // Enter / Space activate the card when it's rendered as a plain
  // <article role="button"> instead of a router-link.
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    emit("click", e as unknown as MouseEvent);
  }
}

// Reverse-morph (paint the view-transition-name when GameDetails is
// leaving) is handled by GameCover via its `morph-id` prop below.
</script>

<template>
  <component
    :is="decorative ? 'div' : static ? 'article' : 'router-link'"
    :to="static || decorative ? undefined : href"
    :role="static && !decorative ? 'button' : undefined"
    :tabindex="static && !decorative ? 0 : undefined"
    class="r-gc"
    :class="[
      size !== 'md' && `r-gc--size-${size}`,
      {
        'r-gc--hero': hero,
        'r-gc--focused': focused,
        'r-gc--static': static || decorative,
        'r-gc--no-hover': noHover || decorative,
        'r-gc--selected': isSelected,
        'r-gc--checkbox-on': checkboxAlwaysOn,
        'r-gc--has-platform-icon': !static && !decorative && showPlatformIcon,
        'r-gc--alt-art': isAltStyle,
      },
    ]"
    :style="{ '--r-cover-ratio': coverAspectRatio }"
    :aria-label="decorative ? undefined : title"
    :aria-pressed="
      decorative
        ? undefined
        : static
          ? selected
          : selectable
            ? isSelected
            : undefined
    "
    :data-rom-id="rom.id"
    :data-focus-key="!decorative && !static ? `rom-${rom.id}` : undefined"
    @click.capture="onCardClickCapture"
    @click="onCardClick"
    @keydown="static && !decorative ? onStaticKeydown($event) : undefined"
    @mouseenter="onCoverEnter"
    @mouseleave="onCoverLeave"
    @focus="onCoverFocus"
    @blur="onCoverBlur"
    @pointerdown="onCardPointerDown"
    @pointermove="onCardPointerMove"
    @pointerup="onCardPointerEnd"
    @pointercancel="onCardPointerEnd"
  >
    <GameCover
      ref="coverRef"
      class="r-gc__art"
      :rom="rom"
      :title="title"
      :identified="rom.is_identified"
      :cover-src="coverSrc"
      :webp="webp"
      :active="coverActive"
      :morph-id="isSynthetic ? null : rom.id"
    >
      <!-- Selection checkbox — top-left, drawn over the cover. Hidden
           at rest; appears on hover for discoverability, and stays
           pinned whenever the gallery is in selection mode so the
           user always knows which cards are picked. Uses RCheckbox
           in bare/circle mode so the check + glow + press squash
           animations come straight from the primitive. The wrapper
           click intercepts the label's native input toggle so the
           store (not the input element) drives state. -->
      <RCheckbox
        v-if="showCheckbox"
        class="r-gc__check"
        :model-value="isSelected"
        shape="circle"
        size="md"
        color="primary"
        bare
        hide-details
        tabindex="-1"
        @click="onCheckboxClick"
      />

      <!-- Consumer-driven overlay slot — sits above the cover, below
           the gallery chrome. Use for badges that aren't part of the
           default overlay set (provider logos, custom status pills). -->
      <div v-if="$slots.overlay" class="r-gc__overlay-slot">
        <slot name="overlay" />
      </div>

      <!-- Gallery chrome — all suppressed in static / decorative mode. -->
      <template v-if="!static && !decorative">
        <div v-if="ratingLabel" class="r-gc__rating">★ {{ ratingLabel }}</div>

        <RBtn
          v-if="showPlatformIcon"
          icon
          size="x-small"
          variant="text"
          class="r-gc__platform-icon"
          :aria-label="
            t('platform.browse-platform', { platform: platformShort })
          "
          @click="onPlatformClick"
        >
          <RPlatformIcon
            :slug="rom.platform_slug"
            :fs-slug="rom.platform_fs_slug"
            :alt="platformShort"
            :size="22"
          />
        </RBtn>

        <GameActionBtn
          :rom="rom"
          action="status"
          size="small"
          orientation="vertical"
        />

        <SiblingBadge :rom="rom" />

        <!-- Hover overlay — action buttons are the shared GameActionBtn. -->
        <div class="r-gc__overlay">
          <div class="r-gc__overlay-center">
            <GameActionBtn
              v-if="actions.canPlay.value"
              :rom="rom"
              action="play"
              variant="emphasized"
            />
          </div>

          <div class="r-gc__overlay-bottom">
            <GameActionBtn :rom="rom" action="download" size="small" />
            <GameActionBtn :rom="rom" action="collection" size="small" />
            <GameActionBtn :rom="rom" action="favorite" size="small" />
            <GameActionBtn :rom="rom" action="more" size="small" />
          </div>
        </div>
      </template>
    </GameCover>
    <div v-if="showTitle" class="r-gc__label">
      {{ title }}
    </div>
    <!-- Full-name tooltip — the label below the cover truncates at one
         line (two on hero variant), so a hover reveal is the only way
         to see the full title without navigating in. `activator="parent"`
         attaches to the root card element so the tooltip fires no
         matter which part of the card the user hovers; the open delay
         keeps it from flashing during fast scans across the gallery. -->
    <RTooltip
      v-if="showTitle"
      activator="parent"
      :text="title"
      location="top"
      :open-delay="500"
    />
  </component>
</template>

<style scoped>
.r-gc {
  flex-shrink: 0;
  cursor: pointer;
  position: relative;
  outline: none;
  width: var(--r-card-art-w);
  /* Width is the card-art token exactly — never let a stray border /
     padding push the rendered box past it (which would eat the grid gap
     and make neighbouring covers appear to touch). */
  box-sizing: border-box;
  text-decoration: none;
  color: var(--r-color-fg);
}

/* Default (gallery) card derives its art height from the active cover
   ratio so the boxart style drives the shape (cover_path 2/3, box3d 3/4,
   physical / miximage 1/1). Explicit size tiers + hero keep their fixed
   footprints — they set `--r-card-art-h` directly. `--r-cover-ratio` is
   set inline by `useCoverArt`; the fallback keeps standalone cards sane. */
.r-gc:not([class*="r-gc--size-"]):not(.r-gc--hero) {
  --r-card-art-h: calc(var(--r-card-art-w) / var(--r-cover-ratio, 0.6667));
}

/* The art box IS the shared <GameCover> (this class lands on its root).
   GameCover owns the radius / overflow / background / image; the card
   keeps only the gallery-level box concerns: footprint (height — width
   comes from `.r-gc`), the focus outline, and the hover/focus transition. */
.r-gc__art {
  height: var(--r-card-art-h);
  box-sizing: border-box;
  outline: 2.5px solid transparent;
  outline-offset: 3px;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

/* Alt-art styles (box3d / physical / miximage) drop the card frame so the
   artwork floats: GameCover already makes its own background transparent;
   here we kill the hover / focus / selected DROP SHADOW so a transparent
   disc doesn't get a rectangular shadow around empty space (most obvious
   on the wide hero — Home "continue playing"). The hover scale + the
   focus/selected brand OUTLINE (the `outline` property, not the shadow)
   stay. `!important` beats the multi-state shadow selectors without
   duplicating their whole list. */
.r-gc--alt-art .r-gc__art {
  box-shadow: none !important;
}
/* …and no darkening scrim on hover — the gradient would paint a dark
   rectangle around a floating disc / cartridge. The overlay's controls
   still appear (the emphasized Play CTA carries its own background). */
.r-gc--alt-art .r-gc__overlay {
  background: none;
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
  /* Shrink-wrap around the platform icon. RBtn's size classes try to
     impose a fixed `height` / `width: var(--r-btn-rest-h)` — we have
     to defeat those so the badge always fits whatever `:size` the
     RPlatformIcon was given (icon + 3px padding all around). */
  width: auto !important;
  height: auto !important;
  min-width: 0 !important;
  min-height: 0 !important;
  padding: 3px !important;
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
/* The inner button content must also shrink-wrap so the padded area
   centres the icon symmetrically instead of letting `.r-btn__content`
   inherit any stretched cross-axis sizing. `line-height: 0` kills the
   stray baseline gap an inline-block image would otherwise add at the
   bottom (cause of the "not centred" feel even at small sizes). */
.r-gc__platform-icon :deep(.r-btn__content) {
  line-height: 0;
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

/* Hover-driven art scale gated to mouse/touch — a cursor parked from a
   previous mouse session shouldn't compete with the focused card when
   the user is on a gamepad. Focus / pinned / sibling-pinned states
   trigger the same effect in every modality. */
html[data-input="mouse"] .r-gc:hover .r-gc__art,
html[data-input="touch"] .r-gc:hover .r-gc__art,
.r-gc:focus-visible .r-gc__art,
.r-gc--focused .r-gc__art,
.r-gc:has(.r-v2-game-btn--pinned) .r-gc__art,
.r-gc:has(.sibling-badge--pinned) .r-gc__art {
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
html[data-input="mouse"] .r-gc:hover .r-gc__overlay,
html[data-input="touch"] .r-gc:hover .r-gc__overlay,
.r-gc:focus-visible .r-gc__overlay,
.r-gc--focused .r-gc__overlay,
.r-gc:has(.r-v2-game-btn--pinned) .r-gc__overlay,
.r-gc:has(.sibling-badge--pinned) .r-gc__overlay {
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
html[data-input="mouse"] .r-gc:hover .r-gc__badge,
html[data-input="touch"] .r-gc:hover .r-gc__badge,
.r-gc:focus-visible .r-gc__badge,
.r-gc--focused .r-gc__badge,
.r-gc:has(.r-v2-game-btn--pinned) .r-gc__badge,
.r-gc:has(.sibling-badge--pinned) .r-gc__badge,
html[data-input="mouse"] .r-gc:hover .r-gc__rating,
html[data-input="touch"] .r-gc:hover .r-gc__rating,
.r-gc:focus-visible .r-gc__rating,
.r-gc--focused .r-gc__rating,
.r-gc:has(.r-v2-game-btn--pinned) .r-gc__rating,
.r-gc:has(.sibling-badge--pinned) .r-gc__rating {
  opacity: 1;
}

/* Status badge — corner of the cover that mirrors the platform
   icon. The actual <button> lives inside GameActionBtn's RMenu
   activator slot, so we reach it via `:deep` matching the action
   class. Default position (no platform icon shown): top-left.
   When the platform icon IS shown (the normal gallery layout) the
   badge moves to the right side, just below the platform icon, so
   the selection checkbox can own the top-left corner unambiguously
   and the two right-side affordances stack vertically. Visibility:
   - status set     → always visible (`--active-status`)
   - status not set → invisible by default; fades in on card hover. */
.r-gc :deep(.r-v2-game-btn--action-status) {
  position: absolute;
  top: 7px;
  left: 7px;
  z-index: 2;
  opacity: 0;
}
.r-gc--has-platform-icon :deep(.r-v2-game-btn--action-status) {
  /* Drop below the platform icon (top: 7px + ~28px height + 4px gap
     ≈ 39px). Right-edge alignment matches the platform icon above
     so the two badges read as a vertical stack. */
  top: 40px;
  left: auto;
  right: 7px;
}
html[data-input="mouse"] .r-gc:hover :deep(.r-v2-game-btn--action-status),
html[data-input="touch"] .r-gc:hover :deep(.r-v2-game-btn--action-status),
.r-gc:focus-visible :deep(.r-v2-game-btn--action-status),
.r-gc--focused :deep(.r-v2-game-btn--action-status),
.r-gc:has(.r-v2-game-btn--pinned) :deep(.r-v2-game-btn--action-status),
.r-gc:has(.sibling-badge--pinned) :deep(.r-v2-game-btn--action-status),
.r-gc :deep(.r-v2-game-btn--active-status) {
  opacity: 1;
}

/* Sibling-versions badge — right-side stack with the platform icon
   and status badge. With a platform icon present (the normal gallery
   layout) the chip drops below it; without one it takes the top-right
   corner. When the sibling badge IS present, the status badge slides
   one more notch down so all three affordances read as a clean
   vertical column. */
.r-gc :deep(.sibling-badge) {
  position: absolute;
  top: 7px;
  right: 7px;
  z-index: 3;
}
.r-gc--has-platform-icon :deep(.sibling-badge) {
  top: 40px;
}
.r-gc--has-platform-icon:has(.sibling-badge)
  :deep(.r-v2-game-btn--action-status) {
  /* Sibling pill is ~35px tall (top 40 → bottom 75); the status badge
     sits 5px below to keep the same rhythm as the platform-icon →
     sibling gap. */
  top: 80px;
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
html[data-input="mouse"] .r-gc:hover .r-gc__label,
html[data-input="touch"] .r-gc:hover .r-gc__label,
.r-gc:focus-visible .r-gc__label,
.r-gc--focused .r-gc__label,
.r-gc:has(.r-v2-game-btn--action-more[aria-expanded="true"]) .r-gc__label,
.r-gc:has(.sibling-badge--pinned) .r-gc__label {
  color: var(--r-color-fg);
}

/* ── Hero (16:9) variant ──────────────────────────────────── */
.r-gc--hero {
  width: var(--r-hero-w);
}
.r-gc--hero .r-gc__art {
  /* Width comes from `.r-gc--hero` (GameCover fills it); height is the
     explicit hero footprint, which wins over GameCover's aspect-ratio.
     Radius is passed through GameCover's `--r-cover-radius`. */
  height: var(--r-hero-h);
  --r-cover-radius: var(--r-radius-lg);
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

/* ── Selection checkbox ────────────────────────────────────
   Top-left affordance. The visible chrome (box, fill, draw-in
   tick, press squash) all comes from RCheckbox — this rule
   only owns the positioning and the visibility fade.
   At rest the checkbox is invisible; it fades in on hover or
   focus, and stays pinned whenever the gallery is in selection
   mode (`--checkbox-on`). */
.r-gc__check {
  position: absolute;
  top: 7px;
  left: 7px;
  z-index: 4;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
html[data-input="mouse"] .r-gc:hover .r-gc__check,
html[data-input="touch"] .r-gc:hover .r-gc__check,
.r-gc:focus-visible .r-gc__check,
.r-gc--focused .r-gc__check,
.r-gc--checkbox-on .r-gc__check,
.r-gc--selected .r-gc__check {
  opacity: 1;
  pointer-events: auto;
}

/* Glassy scrim under the unchecked box so the outline reads over
   busy cover art — RCheckbox's default border colour assumes a
   plain page background, here it sits on photos. Once checked the
   primitive's brand fill takes over and we step out of the way. */
.r-gc__check :deep(.r-checkbox__box) {
  background: var(--r-color-overlay-scrim-strong);
  border-color: var(--r-color-overlay-border-strong);
}
.r-gc__check.r-checkbox--checked :deep(.r-checkbox__box),
.r-gc__check.r-checkbox--indeterminate :deep(.r-checkbox__box) {
  /* Let RCheckbox's checked styles win — clear our scrim overrides
     so the brand fill + glow apply unmodified. */
  background: var(--r-color-brand-primary);
  border-color: var(--r-color-brand-primary);
}

/* ── Size tiers ───────────────────────────────────────────────
   Each class only overrides the `--r-card-art-w/h` (and hero pair)
   locally on the card, so every downstream rule that already reads
   those vars (`.r-gc { width }`, `.r-gc__art { width / height }`,
   `.r-gc--hero .r-gc__art`) picks up the new values without
   duplication. "md" is the default — no class — so the gallery
   grid (which reads the global `--r-card-art-w`) stays in lock-step
   with the un-tiered card. */
.r-gc--size-xs {
  --r-card-art-w: var(--r-card-art-w-xs);
  --r-card-art-h: var(--r-card-art-h-xs);
  --r-hero-w: var(--r-hero-w-xs);
  --r-hero-h: var(--r-hero-h-xs);
}
.r-gc--size-sm {
  --r-card-art-w: var(--r-card-art-w-sm);
  --r-card-art-h: var(--r-card-art-h-sm);
  --r-hero-w: var(--r-hero-w-sm);
  --r-hero-h: var(--r-hero-h-sm);
}
.r-gc--size-lg {
  --r-card-art-w: var(--r-card-art-w-lg);
  --r-card-art-h: var(--r-card-art-h-lg);
  --r-hero-w: var(--r-hero-w-lg);
  --r-hero-h: var(--r-hero-h-lg);
}
.r-gc--size-xl {
  --r-card-art-w: var(--r-card-art-w-xl);
  --r-card-art-h: var(--r-card-art-h-xl);
  --r-hero-w: var(--r-hero-w-xl);
  --r-hero-h: var(--r-hero-h-xl);
}

/* ── Mobile ───────────────────────────────────────────────────
   Forces a tighter footprint on phones. Only applies to the
   default (md) card — explicit size tiers are intentional choices
   from the consumer (an `xs` list-row avatar should stay 48px even
   on mobile). Sets the vars instead of `width` directly so the
   inner `.r-gc__art` rule picks them up too. */
html[data-bp~="xs"] .r-gc:not([class*="r-gc--size-"]) {
  --r-card-art-w: 130px;
  /* height derives from --r-cover-ratio (see the default-card rule above) */
  --r-hero-w: 220px;
  --r-hero-h: 124px;
}
html[data-bp~="xs"] .r-gc__label {
  font-size: 11px;
}
/* Actions always visible on touch (no hover) */
html[data-bp~="xs"] .r-gc__overlay-bottom {
  opacity: 1;
}
</style>
