<script setup lang="ts">
// Grid view — gallery-style layout.
//
// Grid of result cards stays visible at all times. Clicking a card
// lifts it, blurs the rest of the grid and overlays a focused panel
// over the body with cover-source picker + rename + confirm. Click
// the backdrop or press Esc to close.
import { RBtn, REmptyState, RIcon, RProgressCircular } from "@v2/lib";
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { SearchRom, SimpleRom } from "@/stores/roms";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import MatchRomRenameToggle from "@/v2/components/MatchRom/MatchRomRenameToggle.vue";
import {
  type ConfirmPayload,
  firstAvailableCover,
  getMatchSources,
  matchKey,
  type MatchedSource,
} from "@/v2/components/MatchRom/types";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom | null;
  results: SearchRom[];
  searching: boolean;
  searched: boolean;
}>();

const emit = defineEmits<{
  (e: "confirm", payload: ConfirmPayload): void;
}>();

const { t } = useI18n();

const activeKey = ref<string | null>(null);
const selectedSource = ref<MatchedSource | undefined>(undefined);
const renameFromSource = ref(false);

const activeMatch = computed<SearchRom | null>(
  () => props.results.find((r) => matchKey(r) === activeKey.value) ?? null,
);

const activeSources = computed<MatchedSource[]>(() =>
  activeMatch.value ? getMatchSources(activeMatch.value) : [],
);

// Confirm gate — `selectedSource` is required only when the picked
// match actually has covers to choose from. Match results that ship
// without any provider cover (e.g. IGDB metadata-only entries) would
// otherwise leave the button permanently disabled.
const canConfirm = computed(
  () =>
    !!activeMatch.value &&
    (activeSources.value.length === 0 || !!selectedSource.value),
);

function open(r: SearchRom) {
  activeKey.value = matchKey(r);
  const sources = getMatchSources(r);
  selectedSource.value = sources.length === 1 ? sources[0] : undefined;
  renameFromSource.value = false;
}

function close() {
  activeKey.value = null;
  selectedSource.value = undefined;
  renameFromSource.value = false;
}

function confirm() {
  if (!canConfirm.value || !activeMatch.value) return;
  emit("confirm", {
    matchedRom: activeMatch.value,
    cover: selectedSource.value,
    renameFromSource: renameFromSource.value,
  });
}

// When the focus overlay is open it registers on the shared escape
// stack — pressing Esc dismisses just the overlay, leaving the parent
// RDialog open (the user can press Esc again to close that). Without
// the stack, the dialog's own global Esc listener would fire first
// and close everything at once.
const overlayEscEntry: EscapableEntry = {
  close: () => close(),
  persistent: false,
};
watch(activeKey, (value) => {
  if (value !== null) pushEscapable(overlayEscEntry);
  else popEscapable(overlayEscEntry);
});
onBeforeUnmount(() => popEscapable(overlayEscEntry));

watch(
  () => props.results,
  () => close(),
);
</script>

<template>
  <div v-if="searching" class="match-grid__state">
    <RProgressCircular indeterminate :size="40" />
  </div>

  <REmptyState
    v-else-if="searched && !results.length"
    icon="mdi-disc-alert"
    :title="t('common.no-results')"
    :hint="t('rom.results-found')"
  />

  <div v-else-if="!searched" class="match-grid__state">
    <REmptyState
      icon="mdi-magnify-scan"
      :title="t('rom.match-search-title')"
      :hint="t('rom.match-search-hint')"
    />
  </div>

  <div v-else class="match-grid">
    <div
      class="match-grid__grid"
      :class="{ 'match-grid__grid--dim': activeKey !== null }"
      :inert="activeKey !== null ? true : undefined"
    >
      <!-- Wrapper carries the stagger animation. We can't paint it
           directly on GameCard because its root is a dynamic
           `<component :is>` and the scoped `data-v` hash doesn't
           always reach the inner element — the animation rule never
           matches. A plain <div> in this template's own scope
           sidesteps that and acts as the grid cell, while GameCard
           sits inside at its natural width. -->
      <div
        v-for="(r, i) in results"
        :key="matchKey(r)"
        class="match-grid__card-cell"
        :style="{ '--i': i }"
      >
        <GameCard
          :rom="r as unknown as SimpleRom"
          :cover-src="firstAvailableCover(r)"
          static
          class="match-grid__card"
          :class="{ 'match-grid__card--active': activeKey === matchKey(r) }"
          @click="open(r)"
        />
      </div>
    </div>

    <Transition name="match-grid">
      <div v-if="activeMatch" class="match-grid__overlay">
        <!-- Full-area scrim is a real <button> so clicking the dim
             area dismisses the overlay without tripping the lint
             rule for click handlers on static elements. Tab-index -1
             keeps it out of the focus order; Escape (handled globally
             above) is the keyboard equivalent. -->
        <button
          type="button"
          class="match-grid__scrim"
          tabindex="-1"
          :aria-label="t('common.close')"
          @click="close"
        />
        <section class="match-grid__panel" :aria-label="t('rom.details')">
          <header class="match-grid__head">
            <h3 class="match-grid__title">{{ activeMatch.name }}</h3>
            <RBtn
              icon="mdi-close"
              size="small"
              variant="outlined"
              :aria-label="t('common.close')"
              :tooltip="t('common.close')"
              @click="close"
            />
          </header>

          <p v-if="activeMatch.summary" class="match-grid__summary">
            {{ activeMatch.summary }}
          </p>

          <p v-if="activeSources.length > 1" class="match-grid__sources-label">
            {{ t("rom.pick-cover") }}
          </p>

          <p
            v-if="activeSources.length === 0"
            class="match-grid__sources-empty"
          >
            {{ t("rom.match-no-cover-info") }}
          </p>

          <div v-if="activeSources.length" class="match-grid__sources">
            <button
              v-for="(s, i) in activeSources"
              :key="s.name"
              type="button"
              class="match-grid__source"
              :class="{
                'match-grid__source--selected': selectedSource?.name === s.name,
              }"
              :style="{ '--i': i }"
              @click="selectedSource = s"
            >
              <img
                :src="s.url_cover"
                :alt="s.name"
                class="match-grid__source-img"
              />
              <span class="match-grid__source-badge">
                <img :src="s.logo_path" :alt="s.name" />
              </span>
              <span
                v-if="selectedSource?.name === s.name"
                class="match-grid__source-check"
                aria-hidden
              >
                <RIcon icon="mdi-check" size="14" />
              </span>
            </button>
          </div>

          <div class="match-grid__footer">
            <MatchRomRenameToggle
              v-model="renameFromSource"
              :rom="rom"
              :matched-name="activeMatch.name"
            />

            <div class="match-grid__cta">
              <RBtn
                variant="flat"
                color="primary"
                prepend-icon="mdi-check"
                :disabled="!canConfirm"
                @click="confirm"
              >
                {{ t("rom.match-this-game") }}
              </RBtn>
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.match-grid__state {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 200px;
}

.match-grid {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.match-grid__grid {
  /* Grid is the scroller — body itself doesn't scroll, so the overlay
     (absolute, anchored to the variant root) stays put while the user
     scrolls cards behind it. Padding gives GameCard's hover scale +
     brand outline room before the scroll container clips it. */
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
  padding: 10px 8px 6px;
  /* Flow-pack of natural-width cards (like the gallery) rather than a rigid
     uniform-width grid — each GameCard renders at its cover's true aspect, so
     a wide cover would spill out of a fixed grid cell. */
  display: flex;
  flex-wrap: wrap;
  gap: 18px 14px;
  align-content: start;
  transition:
    filter 260ms ease,
    transform 260ms ease;
}
.match-grid__grid--dim {
  filter: blur(4px) brightness(0.55);
  transform: scale(0.985);
  pointer-events: none;
  user-select: none;
}

.match-grid__card-cell {
  /* Shrink-wrap the card's natural width and never shrink below it (a fixed
     -height card shrunk on the cross axis would crop its cover). */
  flex: 0 0 auto;
  /* Lay the card out as a flex item (not a block child). GameCard derives its
     width from a fixed height via the cover's `aspect-ratio`; as a block child
     of a shrink-to-fit cell that width resolution is circular, and WebKit
     (Safari) collapses it to a thin sliver. Flex intrinsic sizing resolves it
     correctly, the same path the gallery row already relies on. */
  display: flex;
  /* …but never wider than the grid: a wide cover (landscape provider art, or
     a card wider than a narrow phone) draws its width from the cover aspect
     and is otherwise unbounded, so it would spill past the right edge. Cap it
     to the container so it scales down to fit instead. */
  max-width: 100%;
  min-width: 0;
  /* Stagger entrance — same vocabulary the cover-source picker uses,
     so opening the dialog and selecting a match share a consistent
     "cascading reveal" feel. `--i` is the card's index, set inline. */
  animation: match-grid-card-in 420ms cubic-bezier(0.34, 1.56, 0.64, 1)
    backwards;
  animation-delay: calc(var(--i, 0) * 35ms);
}
/* Propagate the cap through the card to its cover art box (fixed height,
   naturally-derived width) so the cap actually bounds the rendered cover. */
.match-grid__card,
.match-grid__card :deep(.r-gc__art) {
  max-width: 100%;
}
@keyframes match-grid-card-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.match-grid__card {
  cursor: pointer;
  transition: opacity 220ms ease;
}
.match-grid__card--active {
  /* The active card stays unblurred under the panel — useful as the
     spatial anchor. We bump its z-index above the dim layer and let
     the overlay overlay above it carry the conversation. */
  position: relative;
  z-index: 2;
  opacity: 0;
}

/* ── Overlay panel ───────────────────────────────────────── */
.match-grid__overlay {
  position: absolute;
  inset: -18px -16px;
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 5;
}

.match-grid__scrim {
  position: absolute;
  inset: 0;
  appearance: none;
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 55%,
    transparent
  );
  border: none;
  cursor: pointer;
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}

.match-grid__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: min(640px, 100%);
  max-height: 100%;
  overflow-y: auto;
  scrollbar-width: thin;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, var(--r-color-panel)) 0%,
    var(--r-color-panel) 100%
  );
  border: 1px solid var(--r-color-brand-primary);
  border-radius: var(--r-radius-card);
  padding: 18px 20px 20px;
  box-shadow:
    0 30px 80px color-mix(in srgb, black 60%, transparent),
    0 0 0 6px color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
}

.match-grid__head {
  /* Title + close button on the same row; the summary lives outside
     this header so it can stretch to the full panel width below. */
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.match-grid__title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.match-grid__summary {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--r-color-fg-secondary);
  max-height: 120px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.match-grid__sources-label {
  margin: 0;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.match-grid__sources-empty {
  margin: 0;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--r-color-fg-muted);
  background: var(--r-color-bg-elevated);
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.match-grid__sources {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  justify-content: center;
}

.match-grid__source {
  appearance: none;
  position: relative;
  display: grid;
  place-items: center;
  /* Reserve roughly a 2:3 slot so the tile doesn't collapse before the
     source cover loads; it grows to the cover's true width on load. */
  min-width: 114px;
  background: transparent;
  border: 2px solid transparent;
  border-radius: calc(var(--r-radius-art) + 2px);
  padding: 3px;
  cursor: pointer;
  outline: none;
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
  animation: match-source-in 380ms cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
  animation-delay: calc(var(--i, 0) * 55ms + 140ms);
}
.match-grid__source:hover {
  transform: translateY(-3px) scale(1.05);
}
.match-grid__source--selected {
  border-color: var(--r-color-brand-primary);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent),
    0 10px 26px
      color-mix(in srgb, var(--r-color-brand-primary) 40%, transparent);
}
@keyframes match-source-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.82);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.match-grid__source-img {
  display: block;
  /* Fixed height, natural width — the tile takes the cover's true aspect,
     never cropped (matches the gallery cards). `max-width` caps the rare
     ultra-wide cover to the tile so it letterboxes instead of overflowing
     and getting clipped by the panel. */
  height: 162px;
  width: auto;
  max-width: 100%;
  object-fit: contain;
  border-radius: var(--r-radius-art);
  background: var(--r-color-cover-placeholder);
}
.match-grid__source-badge {
  position: absolute;
  top: 5px;
  left: 5px;
  width: 28px;
  height: 28px;
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 90%,
    transparent
  );
  border: 1px solid var(--r-color-overlay-border);
  border-radius: var(--r-radius-sm);
  padding: 3px;
  display: grid;
  place-items: center;
}
.match-grid__source-badge img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.match-grid__source-check {
  position: absolute;
  bottom: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  background: var(--r-color-brand-primary);
  color: var(--r-color-overlay-fg);
  border-radius: 50%;
  display: grid;
  place-items: center;
  box-shadow: 0 2px 8px color-mix(in srgb, black 40%, transparent);
  animation: match-check-pop 320ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes match-check-pop {
  0% {
    opacity: 0;
    transform: scale(0.3);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.match-grid__footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
}
.match-grid__cta {
  display: flex;
  justify-content: flex-end;
}

/* Overlay enter/leave — scrim fades, panel scales + lifts. */
.match-grid-enter-active,
.match-grid-leave-active {
  transition:
    opacity 220ms ease,
    backdrop-filter 220ms ease;
}
.match-grid-enter-active .match-grid__panel,
.match-grid-leave-active .match-grid__panel {
  transition:
    opacity 240ms ease,
    transform 320ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.match-grid-enter-from,
.match-grid-leave-to {
  opacity: 0;
}
.match-grid-enter-from .match-grid__panel,
.match-grid-leave-to .match-grid__panel {
  opacity: 0;
  transform: scale(0.92) translateY(12px);
}
</style>
