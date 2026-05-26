<script setup lang="ts">
// List view — master/detail layout.
//
// Left column: condensed list of matches (mini cover + title + provider
// chips). Right column: detail panel for the currently picked match —
// summary, source-cover picker, rename toggle and a sticky confirm.
// In xs the columns stack with the detail panel below the list.
import { RBtn, REmptyState, RIcon, RProgressCircular } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { SearchRom, SimpleRom } from "@/stores/roms";
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

const selectedKey = ref<string | null>(null);
const selectedSource = ref<MatchedSource | undefined>(undefined);
const renameFromSource = ref(false);

const selectedMatch = computed<SearchRom | null>(
  () => props.results.find((r) => matchKey(r) === selectedKey.value) ?? null,
);

const selectedSources = computed<MatchedSource[]>(() =>
  selectedMatch.value ? getMatchSources(selectedMatch.value) : [],
);

// Confirm gate — `selectedSource` is required only when the picked
// match actually has covers to choose from. Match results that ship
// without any provider cover (e.g. IGDB metadata-only entries) would
// otherwise leave the button permanently disabled.
const canConfirm = computed(
  () =>
    !!selectedMatch.value &&
    (selectedSources.value.length === 0 || !!selectedSource.value),
);

function providerLogos(r: SearchRom): Array<{ name: string; logo: string }> {
  return getMatchSources(r).map((s) => ({ name: s.name, logo: s.logo_path }));
}

function select(r: SearchRom) {
  selectedKey.value = matchKey(r);
  const sources = getMatchSources(r);
  selectedSource.value = sources.length === 1 ? sources[0] : undefined;
  renameFromSource.value = false;
}

function confirm() {
  if (!canConfirm.value || !selectedMatch.value) return;
  emit("confirm", {
    matchedRom: selectedMatch.value,
    cover: selectedSource.value,
    renameFromSource: renameFromSource.value,
  });
}

watch(
  () => props.results,
  () => {
    selectedKey.value = null;
    selectedSource.value = undefined;
    renameFromSource.value = false;
  },
);
</script>

<template>
  <div v-if="searching" class="match-list__state">
    <RProgressCircular indeterminate :size="40" />
  </div>

  <REmptyState
    v-else-if="searched && !results.length"
    icon="mdi-disc-alert"
    :title="t('common.no-results')"
    :hint="t('rom.results-found')"
  />

  <div v-else-if="!searched" class="match-list__state">
    <REmptyState
      icon="mdi-magnify-scan"
      title="Search for a match"
      hint="Adjust the name above and hit Search to look up metadata across the enabled providers."
    />
  </div>

  <div v-else class="match-list">
    <!-- ── Left: condensed list ──────────────────────────────── -->
    <ul class="match-list__list" role="listbox" aria-label="Search matches">
      <li
        v-for="(r, i) in results"
        :key="matchKey(r)"
        class="match-list__row-li"
        :style="{ '--i': i }"
      >
        <button
          type="button"
          class="match-list__row"
          :class="{
            'match-list__row--selected': selectedKey === matchKey(r),
          }"
          :aria-selected="selectedKey === matchKey(r)"
          @click="select(r)"
        >
          <span class="match-list__row-cover">
            <img
              v-if="firstAvailableCover(r)"
              :src="firstAvailableCover(r) ?? undefined"
              :alt="r.name ?? 'cover'"
            />
            <span v-else class="match-list__row-cover-placeholder">
              {{ (r.name ?? "?").charAt(0) }}
            </span>
          </span>
          <span class="match-list__row-meta">
            <span class="match-list__row-name">{{ r.name }}</span>
            <span class="match-list__row-chips">
              <span
                v-for="p in providerLogos(r)"
                :key="p.name"
                class="match-list__row-chip"
                :title="p.name"
              >
                <img :src="p.logo" :alt="p.name" />
              </span>
            </span>
          </span>
        </button>
      </li>
    </ul>

    <!-- ── Right: detail panel ───────────────────────────────── -->
    <Transition name="match-list-detail" mode="out-in">
      <section
        v-if="selectedMatch"
        :key="selectedKey ?? '_'"
        class="match-list__detail"
        :aria-label="`Details for ${selectedMatch.name}`"
      >
        <header class="match-list__detail-head">
          <h3 class="match-list__detail-title">{{ selectedMatch.name }}</h3>
          <p v-if="selectedMatch.summary" class="match-list__detail-summary">
            {{ selectedMatch.summary }}
          </p>
        </header>

        <div class="match-list__detail-scroll">
          <p
            v-if="selectedSources.length > 1"
            class="match-list__sources-label"
          >
            Pick a cover
          </p>

          <p
            v-if="selectedSources.length === 0"
            class="match-list__sources-empty"
          >
            This match doesn't include cover artwork. You can still apply it —
            the ROM keeps its existing cover.
          </p>

          <div v-if="selectedSources.length" class="match-list__sources">
            <button
              v-for="(s, i) in selectedSources"
              :key="s.name"
              type="button"
              class="match-list__source"
              :class="{
                'match-list__source--selected': selectedSource?.name === s.name,
              }"
              :style="{ '--i': i }"
              @click="selectedSource = s"
            >
              <img
                :src="s.url_cover"
                :alt="s.name"
                class="match-list__source-img"
              />
              <span class="match-list__source-badge">
                <img :src="s.logo_path" :alt="s.name" />
              </span>
              <span
                v-if="selectedSource?.name === s.name"
                class="match-list__source-check"
                aria-hidden
              >
                <RIcon icon="mdi-check" size="14" />
              </span>
            </button>
          </div>
        </div>

        <div class="match-list__detail-foot">
          <MatchRomRenameToggle
            v-model="renameFromSource"
            :rom="rom"
            :matched-name="selectedMatch.name"
          />

          <div class="match-list__cta">
            <RBtn
              variant="flat"
              color="primary"
              prepend-icon="mdi-check"
              :disabled="!canConfirm"
              @click="confirm"
            >
              Match this game
            </RBtn>
          </div>
        </div>
      </section>

      <div v-else class="match-list__detail-empty">
        <RIcon icon="mdi-cursor-default-click-outline" size="44" />
        <p>Select a match on the left to see covers</p>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.match-list__state {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 200px;
}

.match-list {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(0, 1.4fr);
  gap: 18px;
}

/* ── Left column: condensed list ──────────────────────────── */
.match-list__list {
  list-style: none;
  margin: 0;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
  min-height: 0;
  background: color-mix(in srgb, var(--r-color-bg-elevated) 50%, transparent);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.match-list__row-li {
  animation: match-list-row-in 280ms ease-out backwards;
  animation-delay: calc(var(--i, 0) * 18ms);
}
@keyframes match-list-row-in {
  from {
    opacity: 0;
    transform: translateX(-6px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.match-list__row {
  appearance: none;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--r-radius-sm);
  cursor: pointer;
  color: var(--r-color-fg);
  text-align: left;
  font: inherit;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.match-list__row:hover {
  background: var(--r-color-surface-hover);
  transform: translateX(2px);
}
.match-list__row--selected {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border-color: var(--r-color-brand-primary);
}

.match-list__row-cover {
  flex-shrink: 0;
  width: 42px;
  height: 56px;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  display: grid;
  place-items: center;
}
.match-list__row-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.match-list__row-cover-placeholder {
  font-size: 18px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-muted);
}

.match-list__row-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.match-list__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.match-list__row-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.match-list__row-chip {
  width: 18px;
  height: 18px;
  border-radius: var(--r-radius-sm);
  background: color-mix(in srgb, var(--r-color-fg) 8%, transparent);
  padding: 2px;
  display: grid;
  place-items: center;
}
.match-list__row-chip img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* ── Right column: detail ─────────────────────────────────── */
.match-list__detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px;
  min-height: 0;
}

.match-list__detail-scroll {
  /* Mini-gallery — only the covers area scrolls; head and foot stay
     pinned to the top / bottom of the detail panel. Padding gives the
     hover scale on source thumbnails room before the scroll container
     clips them. */
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 4px 8px 2px;
}

.match-list__detail-head {
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  padding: 12px 14px;
}
.match-list__detail-title {
  margin: 0;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.match-list__detail-summary {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--r-color-fg-secondary);
  max-height: 120px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.match-list__sources-label {
  margin: 0;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.match-list__sources-empty {
  margin: 0;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--r-color-fg-muted);
  background: var(--r-color-bg-elevated);
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.match-list__sources {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.match-list__source {
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
  animation: match-source-in 360ms cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
  animation-delay: calc(var(--i, 0) * 45ms + 120ms);
}
.match-list__source:hover {
  transform: translateY(-2px) scale(1.04);
}
.match-list__source--selected {
  border-color: var(--r-color-brand-primary);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent),
    0 8px 22px color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
}

@keyframes match-source-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.85);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.match-list__source-img {
  display: block;
  width: 110px;
  height: 148px;
  object-fit: cover;
  border-radius: var(--r-radius-art);
  background: var(--r-color-cover-placeholder);
}
.match-list__source-badge {
  position: absolute;
  top: 5px;
  left: 5px;
  width: 28px;
  height: 28px;
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 88%,
    transparent
  );
  border: 1px solid var(--r-color-overlay-border);
  border-radius: var(--r-radius-sm);
  padding: 3px;
  display: grid;
  place-items: center;
}
.match-list__source-badge img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.match-list__source-check {
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
}

.match-list__detail-foot {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--r-color-border);
}
.match-list__cta {
  display: flex;
  justify-content: flex-end;
}

/* ── Right column: empty state ────────────────────────────── */
.match-list__detail-empty {
  display: grid;
  place-items: center;
  gap: 8px;
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-muted);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}
.match-list__detail-empty p {
  margin: 0;
}

/* Detail panel cross-fade when the picked match changes. */
.match-list-detail-enter-active,
.match-list-detail-leave-active {
  transition:
    opacity 200ms ease,
    transform 240ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.match-list-detail-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.match-list-detail-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Mobile: stack columns ──────────────────────────────── */
html[data-bp~="xs"] .match-list {
  grid-template-columns: 1fr;
  gap: 12px;
}
html[data-bp~="xs"] .match-list__list {
  max-height: 240px;
}
</style>
