<script setup lang="ts">
// Variant C — spotlight.
//
// Grid of result cards stays visible at all times. Clicking a card
// lifts it, blurs the rest of the grid and overlays a "spotlight"
// panel anchored over the body with cover-source picker + rename +
// confirm. Click the backdrop or press Esc to close.
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
  if (!activeMatch.value || !selectedSource.value) return;
  emit("confirm", {
    matchedRom: activeMatch.value,
    cover: selectedSource.value,
    renameFromSource: renameFromSource.value,
  });
}

// Esc key closes the spotlight panel without dismissing the parent
// dialog (RDialog only sees Escape if we don't capture it first).
function onKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && activeKey.value !== null) {
    e.stopPropagation();
    close();
  }
}
if (typeof window !== "undefined") {
  window.addEventListener("keydown", onKeyDown, true);
  onBeforeUnmount(() => window.removeEventListener("keydown", onKeyDown, true));
}

watch(
  () => props.results,
  () => close(),
);
</script>

<template>
  <div v-if="searching" class="match-spot__state">
    <RProgressCircular indeterminate :size="40" />
  </div>

  <REmptyState
    v-else-if="searched && !results.length"
    icon="mdi-disc-alert"
    :title="t('common.no-results')"
    :hint="t('rom.results-found')"
  />

  <div v-else-if="!searched" class="match-spot__state">
    <REmptyState
      icon="mdi-magnify-scan"
      title="Search for a match"
      hint="Adjust the name above and hit Search to look up metadata across the enabled providers."
    />
  </div>

  <div v-else class="match-spot">
    <div
      class="match-spot__grid"
      :class="{ 'match-spot__grid--dim': activeKey !== null }"
      :inert="activeKey !== null ? true : undefined"
    >
      <GameCard
        v-for="(r, i) in results"
        :key="matchKey(r)"
        :rom="r as unknown as SimpleRom"
        :cover-src="firstAvailableCover(r)"
        static
        class="match-spot__card"
        :class="{ 'match-spot__card--active': activeKey === matchKey(r) }"
        :style="{ '--i': i }"
        @click="open(r)"
      />
    </div>

    <Transition name="match-spot">
      <div v-if="activeMatch" class="match-spot__overlay">
        <!-- Full-area scrim is a real <button> so clicking the dim
             area dismisses the spotlight without tripping the lint
             rule for click handlers on static elements. Tab-index -1
             keeps it out of the focus order; Escape (handled globally
             above) is the keyboard equivalent. -->
        <button
          type="button"
          class="match-spot__scrim"
          tabindex="-1"
          aria-label="Close spotlight"
          @click="close"
        />
        <section
          class="match-spot__panel"
          :aria-label="`Match details for ${activeMatch.name}`"
        >
          <header class="match-spot__head">
            <h3 class="match-spot__title">{{ activeMatch.name }}</h3>
            <RBtn
              icon="mdi-close"
              size="small"
              variant="outlined"
              aria-label="Close"
              tooltip="Close"
              @click="close"
            />
          </header>

          <p v-if="activeMatch.summary" class="match-spot__summary">
            {{ activeMatch.summary }}
          </p>

          <p v-if="activeSources.length > 1" class="match-spot__sources-label">
            Pick a cover
          </p>

          <div class="match-spot__sources">
            <button
              v-for="(s, i) in activeSources"
              :key="s.name"
              type="button"
              class="match-spot__source"
              :class="{
                'match-spot__source--selected': selectedSource?.name === s.name,
              }"
              :style="{ '--i': i }"
              @click="selectedSource = s"
            >
              <img
                :src="s.url_cover"
                :alt="s.name"
                class="match-spot__source-img"
              />
              <span class="match-spot__source-badge">
                <img :src="s.logo_path" :alt="s.name" />
              </span>
              <span
                v-if="selectedSource?.name === s.name"
                class="match-spot__source-check"
                aria-hidden
              >
                <RIcon icon="mdi-check" size="14" />
              </span>
            </button>
          </div>

          <div class="match-spot__footer">
            <MatchRomRenameToggle
              v-model="renameFromSource"
              :rom="rom"
              :matched-name="activeMatch.name"
              :disabled="!selectedSource"
            />

            <div class="match-spot__cta">
              <RBtn
                variant="flat"
                color="primary"
                prepend-icon="mdi-check"
                :disabled="!selectedSource"
                @click="confirm"
              >
                Match this game
              </RBtn>
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.match-spot__state {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 200px;
}

.match-spot {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.match-spot__grid {
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
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 18px 14px;
  align-content: start;
  transition:
    filter 260ms ease,
    transform 260ms ease;
}
.match-spot__grid--dim {
  filter: blur(4px) brightness(0.55);
  transform: scale(0.985);
  pointer-events: none;
  user-select: none;
}

.match-spot__card {
  cursor: pointer;
  transition: opacity 220ms ease;
  /* Stagger entrance — same vocabulary the cover-source picker uses,
     so opening the dialog and selecting a match share a consistent
     "cascading reveal" feel. `--i` is the card's index, set inline. */
  animation: match-spot-card-in 420ms cubic-bezier(0.34, 1.56, 0.64, 1)
    backwards;
  animation-delay: calc(var(--i, 0) * 35ms);
}
@keyframes match-spot-card-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
.match-spot__card--active {
  /* The active card stays unblurred under the panel — useful as the
     spatial anchor. We bump its z-index above the dim layer and let
     the spotlight overlay above it carry the conversation. */
  position: relative;
  z-index: 2;
  opacity: 0;
}

/* ── Spotlight overlay ───────────────────────────────────── */
.match-spot__overlay {
  position: absolute;
  inset: -18px -16px;
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 5;
}

.match-spot__scrim {
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

.match-spot__panel {
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

.match-spot__head {
  /* Title + close button on the same row; the summary lives outside
     this header so it can stretch to the full panel width below. */
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.match-spot__title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.match-spot__summary {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--r-color-fg-secondary);
  max-height: 120px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.match-spot__sources-label {
  margin: 0;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.match-spot__sources {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  justify-content: center;
}

.match-spot__source {
  appearance: none;
  position: relative;
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
.match-spot__source:hover {
  transform: translateY(-3px) scale(1.05);
}
.match-spot__source--selected {
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

.match-spot__source-img {
  display: block;
  width: 120px;
  height: 162px;
  object-fit: cover;
  border-radius: var(--r-radius-art);
  background: var(--r-color-cover-placeholder);
}
.match-spot__source-badge {
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
.match-spot__source-badge img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.match-spot__source-check {
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

.match-spot__footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
}
.match-spot__cta {
  display: flex;
  justify-content: flex-end;
}

/* Overlay enter/leave — scrim fades, panel scales + lifts. */
.match-spot-enter-active,
.match-spot-leave-active {
  transition:
    opacity 220ms ease,
    backdrop-filter 220ms ease;
}
.match-spot-enter-active .match-spot__panel,
.match-spot-leave-active .match-spot__panel {
  transition:
    opacity 240ms ease,
    transform 320ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.match-spot-enter-from,
.match-spot-leave-to {
  opacity: 0;
}
.match-spot-enter-from .match-spot__panel,
.match-spot-leave-to .match-spot__panel {
  opacity: 0;
  transform: scale(0.92) translateY(12px);
}
</style>
