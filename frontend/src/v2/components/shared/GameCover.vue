<script setup lang="ts">
// GameCover — the single "game cover" art box, shared by every surface
// that shows a rom's cover (gallery GameCard, GameDetails CoverColumn, the
// EmulatorJS / Ruffle player heroes). It owns everything intrinsic to the
// cover and nothing about the surrounding surface:
//   * cover resolution + aspect ratio + object-fit  (useCoverArt)
//   * the <img>, the hover <video> crossfade, and the procedural
//     placeholder when there's no cover                (CoverPlaceholder)
//   * the alt-art "float on transparent" treatment (box3d / physical /
//     miximage) — no grey box behind a disc / cartridge
//   * hover spin / hover video + the launch "load" flourish (useCoverAnimation)
//   * the shared-element morph paint for back-navigation
//
// Chrome that belongs to a *surface* (gallery overlay buttons, badges,
// selection checkbox, the player glow) is NOT here — consumers drop it
// into the default slot, which renders on top of the cover.
//
// Sizing: the box is `width: 100%` and derives its height from the active
// cover ratio (`aspect-ratio`). A consumer that needs a fixed footprint
// (GameCard's size tiers / hero) just sets an explicit `height` on this
// element via its own class — that wins over `aspect-ratio`. Radius is a
// `--r-cover-radius` var (defaults to the gallery card radius).
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import CoverPlaceholder from "@/v2/components/shared/CoverPlaceholder.vue";
import { revealedCoverSrcs } from "@/v2/components/shared/coverReveal";
import { useCoverAnimation } from "@/v2/composables/useCoverAnimation";
import {
  useCoverArt,
  type BoxartStyle,
  type CoverArtRom,
} from "@/v2/composables/useCoverArt";
import { pendingMorphName } from "@/v2/composables/useViewTransition";

// inheritAttrs stays ON (default): consumers pass a `class` (e.g.
// `r-gc__art`, `r-v2-det-cover__art`) that must land on — and merge with —
// the single root box. Vue always merges fallthrough class/style with the
// root's own bindings, so the cover box ends up with both.

interface Props {
  /** The rom whose cover to show (nullable for pre-fetch states). */
  rom: CoverArtRom | null;
  /** Title — used as the <img> alt and the placeholder text. */
  title: string;
  /** Identified rom (grid placeholder) vs unmatched (question mark). */
  identified?: boolean;
  /** Explicit cover URL override (preview blobs, external provider art).
   *  Renders as plain box art regardless of the gallery style. */
  coverSrc?: string | null;
  /** Force a specific boxart style (defaults to the gallery preference). */
  forceStyle?: BoxartStyle;
  /** Webp override; falls back to `useWebpSupport`. */
  webp?: boolean;
  /** External hover/focus state → drives spin + hover video. The surface
   *  that owns interactivity (GameCard) passes this. */
  active?: boolean;
  /** Self-track pointer hover on the cover box → spin/video, for surfaces
   *  whose cover isn't itself interactive (CoverColumn). Listeners are
   *  attached imperatively (decorative motion, no keyboard affordance). */
  hoverMotion?: boolean;
  /** Shared-element morph tag id (paints `view-transition-name:
   *  rom-cover-<id>`). */
  morphId?: number | string | null;
  /** How the morph tag is painted:
   *   - false (default): GATED — only while this id is the pending
   *     back-navigation target. For the many gallery cards, so just the
   *     back-morph destination paints (one name per screen). The forward
   *     source is tagged imperatively by `morphTransition`.
   *   - true: STATIC — always painted. For the single detail/hero cover,
   *     which is the forward-morph DESTINATION (must already carry the
   *     name when the gallery card navigates in) and the back SOURCE. */
  morphStatic?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  identified: true,
  coverSrc: undefined,
  forceStyle: undefined,
  webp: undefined,
  active: false,
  hoverMotion: false,
  morphId: null,
  morphStatic: false,
});

const emit = defineEmits<{
  /** The rendered image's natural ratio (w / h) once loaded — lets the
   *  gallery's wrapping rows pack by true shape. */
  ratio: [number];
}>();

const art = useCoverArt(() => props.rom, {
  coverSrc: () => props.coverSrc,
  forceStyle: props.forceStyle
    ? () => props.forceStyle as BoxartStyle
    : undefined,
  webp: () => props.webp,
});

const imgError = ref(false);
const showingImage = computed(
  () =>
    !!(art.coverUrl.value || art.fallbackUrl.value) &&
    !(imgError.value && !art.fallbackUrl.value),
);
const showFallback = computed(() => imgError.value && !!art.fallbackUrl.value);
// Alt-art styles float on a transparent box — but only while a real
// image renders; the placeholder keeps the grey backdrop so its title
// stays legible.
const isAltStyle = computed(
  () => art.style.value !== "cover_path" && showingImage.value,
);

const rootEl = ref<HTMLElement | null>(null);
const imgEl = ref<HTMLImageElement | null>(null);
const videoEl = ref<HTMLVideoElement | null>(null);

// Blur-up "bloom" reveal: the cover paints soft + slightly enlarged and
// snaps into focus the moment its bytes land. `coverLoaded` flips on the
// <img> load event; it resets whenever the active source changes so a
// recycled card (virtual scroll) re-plays the reveal for its new art.
const coverLoaded = ref(false);
const activeSrc = computed(() =>
  showFallback.value ? art.fallbackUrl.value : art.coverUrl.value,
);
// Natural ratio (w / h) of the rendered image, measured on load — drives
// the box shape. Null until decoded / for the placeholder (→ style ratio).
const naturalRatio = ref<number | null>(null);
function measureNaturalRatio() {
  const el = imgEl.value;
  if (el && el.naturalWidth > 0 && el.naturalHeight > 0) {
    const r = el.naturalWidth / el.naturalHeight;
    naturalRatio.value = r;
    emit("ratio", r);
  }
}
watch(activeSrc, (src) => {
  // Seed from the session-seen set: a URL we've already bloomed once skips the
  // reveal so a recycled card doesn't re-flash it (and doesn't pay the blur).
  coverLoaded.value = !!src && revealedCoverSrcs.has(src);
  naturalRatio.value = null;
});
const onCoverLoad = () => {
  coverLoaded.value = true;
  if (activeSrc.value) revealedCoverSrcs.add(activeSrc.value);
  measureNaturalRatio();
};
// True ratio once known, else the style ratio as a first guess.
const boxRatio = computed(() => naturalRatio.value ?? art.ratio.value);

const selfHover = ref(false);
const coverActive = computed(
  () => props.active || (props.hoverMotion && selfHover.value),
);

const { isVideoPlaying, playLoad } = useCoverAnimation({
  el: imgEl,
  videoEl,
  animateCD: art.animateCD,
  animateCartridge: art.animateCartridge,
  videoUrl: art.videoUrl,
  motionEnabled: art.motionEnabled,
  active: coverActive,
});

const morphStyle = computed(() => {
  if (props.morphId == null) return undefined;
  const name = `rom-cover-${props.morphId}`;
  // Static: the single detail/hero cover always carries the name (forward
  // destination + back source). Gated: gallery cards paint it only when
  // they're the pending back-morph target.
  if (props.morphStatic) return { viewTransitionName: name };
  return pendingMorphName.value === name
    ? { viewTransitionName: name }
    : undefined;
});

const onEnter = () => {
  selfHover.value = true;
};
const onLeave = () => {
  selfHover.value = false;
};
onMounted(() => {
  // Already bloomed this URL once this session → skip the reveal on this
  // (recycled) mount, regardless of whether the <img> reports `complete` yet.
  if (activeSrc.value && revealedCoverSrcs.has(activeSrc.value)) {
    coverLoaded.value = true;
  }
  // A cached cover can already be decoded before the load listener binds —
  // mark it loaded so the reveal still resolves (it bloom-snaps from the
  // soft initial paint instead of getting stuck blurred).
  if (imgEl.value?.complete && imgEl.value.naturalWidth > 0) {
    coverLoaded.value = true;
    if (activeSrc.value) revealedCoverSrcs.add(activeSrc.value);
    measureNaturalRatio();
  }
  if (!props.hoverMotion) return;
  rootEl.value?.addEventListener("mouseenter", onEnter);
  rootEl.value?.addEventListener("mouseleave", onLeave);
});
onBeforeUnmount(() => {
  rootEl.value?.removeEventListener("mouseenter", onEnter);
  rootEl.value?.removeEventListener("mouseleave", onLeave);
});

defineExpose({
  /** Trigger the one-shot launch flourish (disc drop+spin / cartridge
   *  slot-in). Returns its duration in ms (0 if nothing animates). */
  playLoad,
  /** The cover box DOM node — for the forward view-transition morph. */
  el: () => rootEl.value,
  /** Resolved cover URL (for the background-art highlight). */
  resolvedCover: () => art.coverUrl.value ?? art.fallbackUrl.value,
});
</script>

<template>
  <div
    ref="rootEl"
    class="game-cover"
    :class="{ 'game-cover--alt': isAltStyle }"
    :style="[{ '--r-cover-ratio': boxRatio }, morphStyle]"
  >
    <img
      v-if="showingImage"
      ref="imgEl"
      :src="
        showFallback
          ? (art.fallbackUrl.value ?? undefined)
          : (art.coverUrl.value ?? undefined)
      "
      :alt="title"
      :style="{ objectFit: art.objectFit.value }"
      :class="{
        'game-cover__img--behind': isVideoPlaying,
        'game-cover__img--reveal': !coverLoaded && art.motionEnabled.value,
      }"
      loading="lazy"
      decoding="async"
      @load="onCoverLoad"
      @error="imgError = true"
    />
    <CoverPlaceholder
      v-else
      :name="title"
      :title="title"
      :identified="identified"
    />

    <!-- Hover video (miximage) — crossfades over the still mix image. -->
    <video
      v-if="art.videoUrl.value"
      ref="videoEl"
      class="game-cover__video"
      :class="{ 'game-cover__video--playing': isVideoPlaying }"
      :src="art.videoUrl.value ?? undefined"
      loop
      muted
      playsinline
      preload="none"
    />

    <!-- Surface chrome (gallery overlay / badges / glow) renders on top. -->
    <slot />
  </div>
</template>

<style scoped>
.game-cover {
  position: relative;
  width: 100%;
  /* Height derives from the active cover ratio unless the consumer sets
     an explicit `height` (GameCard tiers / hero), which wins. */
  aspect-ratio: var(--r-cover-ratio, 0.6667);
  border-radius: var(--r-cover-radius, var(--r-radius-art));
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
}
/* Alt-art (box3d / physical / miximage) floats on a transparent box. */
.game-cover--alt {
  background: transparent;
}

/* Direct-child selector so the placeholder's own <img> isn't matched. */
.game-cover > img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  /* Three motions ride this <img>, each on its own property so they never
     clobber each other: opacity crossfades to the hover video, filter +
     scale drive the blur-up reveal on first paint, and the spin owns
     `rotate` (set imperatively in useCoverAnimation). */
  transition:
    opacity 0.35s ease,
    filter 0.6s ease,
    scale 0.65s cubic-bezier(0.22, 1, 0.36, 1);
}
.game-cover__img--behind {
  opacity: 0;
}

/* Blur-up "bloom": the cover lands soft, a touch oversaturated/bright and
   slightly enlarged (the >1 scale tucks the blur halo behind the box edge),
   then snaps into focus as its bytes arrive. Removing the class transitions
   back to the resting cover above. `scale` is the individual property so it
   composes with the spin's `rotate` and the drop-in's `transform`. */
.game-cover__img--reveal {
  opacity: 0;
  filter: blur(16px) saturate(1.5) brightness(1.12);
  scale: 1.05;
}

@media (prefers-reduced-motion: reduce) {
  /* Keep a gentle opacity fade, drop the blur/scale flourish. */
  .game-cover > img {
    transition: opacity 0.25s ease;
  }
  .game-cover__img--reveal {
    filter: none;
    scale: 1;
  }
}

.game-cover__video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.35s ease;
  pointer-events: none;
}
.game-cover__video--playing {
  opacity: 1;
}
</style>
