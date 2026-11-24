<script setup lang="ts">
// PluginSlot: one place plugins may add something. A surface that offers an
// extension point mounts this with the slot's name, so a new surface is a
// manifest value and a mount rather than another component. Two shapes cover
// the surfaces today: icon buttons for a game's action row, and labelled rows
// for lists such as navigation or Settings.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { PluginFactSchema } from "@/__generated__";
import { usePluginFacts } from "@/composables/usePluginFacts";
import {
  usePluginActions,
  type PluginAction,
} from "@/composables/usePluginActions";
import { RIcon, RTooltip } from "@/lib";
import type { SimpleRom } from "@/stores/roms";

const props = withDefaults(
  defineProps<{
    slot: string;
    rom?: SimpleRom | null;
    size?: "default" | "large";
    labelled?: boolean;
  }>(),
  { rom: null, size: "default", labelled: false },
);

const { t } = useI18n();
const { forSlot, open } = usePluginActions(() => props.rom ?? null);
const { factForAction } = usePluginFacts(() => props.rom ?? null);
const actions = computed<PluginAction[]>(() => forSlot(props.slot));

/** The report behind one button, when the manifest says which panel it is. */
function reportFor(action: PluginAction): PluginFactSchema | null {
  return factForAction(action.pluginId, action.id);
}

// Ratings arrive as whatever the source calls them; the tone is decided here,
// because the server has no business knowing what "Perfect" means.
const TONES: Record<string, string> = {
  perfect: "great",
  great: "good",
  playable: "mixed",
};

function toneFor(rating: string): string {
  return TONES[rating.trim().toLowerCase()] ?? "bad";
}

/** The strongest rating a panel holds, for the dot in its header. */
function bestTone(fact: PluginFactSchema): string {
  const totals = new Map<string, number>();
  for (const group of fact.groups ?? []) {
    for (const [rating, count] of Object.entries(group.counts ?? {})) {
      totals.set(rating, (totals.get(rating) ?? 0) + count);
    }
  }
  const best = [...totals.entries()].sort((a, b) => b[1] - a[1])[0];
  return best ? toneFor(best[0]) : "bad";
}

/** The three reports worth naming in a tooltip, biggest first. */
function topGroups(fact: PluginFactSchema): PluginFactSchema["groups"] {
  return (fact.groups ?? []).slice(0, 3);
}

// Best first: a source may hand its ratings over in any order, and a table
// whose columns move between emulators cannot be read down.
const RATING_ORDER = [
  "perfect",
  "great",
  "playable",
  "ingame",
  "intro",
  "loadable",
  "poor",
];

/** The rating columns a tooltip shows, in canonical order: the union across the
 *  emulators it names, so every row has the same columns and a column can be
 *  read down. */
function columns(fact: PluginFactSchema): string[] {
  const seen = new Set<string>();
  for (const group of topGroups(fact)) {
    for (const rating of Object.keys(group.counts ?? {})) seen.add(rating);
  }
  return [...seen].sort(
    (a, b) =>
      RATING_ORDER.indexOf(a.trim().toLowerCase()) -
      RATING_ORDER.indexOf(b.trim().toLowerCase()),
  );
}

/** The grid a row wears: a name column, then one column per rating. Fixed
 *  columns are the only way a chip for one emulator sits under the same chip for
 *  the next, which is what makes the table readable down. */
function gridStyle(fact: PluginFactSchema): Record<string, string> {
  // `auto` sizes a column to its widest cell across the whole grid, so a column
  // is as wide as the longest chip in it and every row starts where the last
  // one did.
  return {
    gridTemplateColumns: `minmax(0, 6.5rem) repeat(${columns(fact).length}, auto)`,
  };
}

/** How many reports the three named emulators leave out. */
function hiddenReports(fact: PluginFactSchema): number {
  const shown = (fact.groups ?? [])
    .slice(0, 3)
    .reduce((total, group) => total + (group.total ?? 0), 0);
  return Math.max((fact.total ?? 0) - shown, 0);
}

function orderedRatings(
  group: NonNullable<PluginFactSchema["groups"]>[number],
): [string, number][] {
  const entries = Object.entries(group.counts ?? {});
  const rank = (rating: string) => {
    const at = RATING_ORDER.indexOf(rating.trim().toLowerCase());
    return at === -1 ? RATING_ORDER.length : at;
  };
  return entries.sort((a, b) => rank(a[0]) - rank(b[0]));
}
</script>

<template>
  <ul v-if="labelled" class="plugin-slot">
    <li v-for="action in actions" :key="`${action.pluginId}:${action.id}`">
      <a
        class="plugin-slot__row"
        :href="action.href"
        :target="action.open === 'same-tab' ? undefined : '_blank'"
        :rel="action.open === 'same-tab' ? undefined : 'noopener noreferrer'"
      >
        <img
          v-if="action.image"
          :src="action.image"
          :alt="action.label"
          class="plugin-slot__logo"
        />
        <RIcon v-else :icon="action.icon" />
        <span>{{ action.label }}</span>
      </a>
    </li>
  </ul>

  <template v-else>
    <button
      v-for="action in actions"
      :key="`${action.pluginId}:${action.id}`"
      type="button"
      class="r-game-btn r-game-btn--surface r-game-btn--action-plugin"
      :class="`r-game-btn--${size}`"
      :aria-label="action.label"
      @click="open(action)"
    >
      <img
        v-if="action.image"
        :src="action.image"
        :alt="action.label"
        class="r-game-btn__img"
      />
      <RIcon v-else :icon="action.icon" />

      <!-- The button opens a report, so hovering it says what the report
           says: the emulators, their ratings, and what a click does. -->
      <template v-if="reportFor(action)">
        <RTooltip
          activator="parent"
          location="top"
          max-width="min(92vw, 640px)"
          :close-delay="160"
          interactive
        >
          <div class="report">
            <header class="report__head">
              <span
                class="report__dot"
                :class="`is-${bestTone(reportFor(action)!)}`"
              />
              <span class="report__title">{{ action.label }}</span>
              <span v-if="reportFor(action)!.total" class="report__total">
                {{
                  t("settings.plugins-facts-reports", {
                    count: reportFor(action)!.total,
                  })
                }}
              </span>
            </header>

            <p v-if="reportFor(action)!.note" class="report__note">
              {{ reportFor(action)!.note }}
            </p>

            <ul
              v-else
              class="report__grid"
              :style="gridStyle(reportFor(action)!)"
            >
              <li
                v-for="group in topGroups(reportFor(action)!)"
                :key="group.key"
                class="report__row"
              >
                <span class="report__name" :title="group.key">{{
                  group.key
                }}</span>
                <span
                  v-for="rating in columns(reportFor(action)!)"
                  :key="rating"
                  class="report__cell"
                >
                  <span
                    v-if="group.counts?.[rating]"
                    class="report__chip"
                    :class="`is-${toneFor(rating)}`"
                  >
                    {{ rating }}<b>{{ group.counts[rating] }}</b>
                  </span>
                  <!-- A column that holds nothing still holds its place, so the
                       table reads down rather than in a ragged edge. -->
                  <span v-else class="report__gap">–</span>
                </span>
              </li>
            </ul>

            <p
              v-if="(reportFor(action)!.groups?.length ?? 0) > 3"
              class="report__note"
            >
              {{
                t("settings.plugins-facts-more", {
                  count: reportFor(action)!.groups!.length - 3,
                  reports: hiddenReports(reportFor(action)!),
                })
              }}
            </p>

            <a
              v-if="reportFor(action)!.link"
              class="report__link"
              :href="reportFor(action)!.link!"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{
                t("settings.plugins-facts-all-count", {
                  count: reportFor(action)!.total,
                })
              }}
              <RIcon icon="mdi-arrow-top-right" size="14" />
            </a>
            <p v-else class="report__note">
              {{ t("settings.plugins-facts-hint") }}
            </p>
          </div>
        </RTooltip>
      </template>
      <RTooltip v-else activator="parent" :text="action.label" location="top" />
    </button>
  </template>
</template>

<style scoped>
.plugin-slot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.plugin-slot__row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: inherit;
  text-decoration: none;
}

.plugin-slot__row:hover {
  text-decoration: underline;
}

/* The tooltip that stands in for the report: a small table, not a paragraph.
   A fixed name column and a fixed order for the chips is what makes three
   emulators comparable at a glance instead of three sentences. */
.report {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 288px;
}

.report__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report__title {
  font-size: 0.88rem;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.report__total {
  margin-inline-start: auto;
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--r-color-tooltip-fg) 10%, transparent);
  color: var(--r-color-tooltip-fg);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
}

.report__note {
  margin: 0;
  color: var(--r-color-tooltip-fg);
  opacity: 0.62;
  font-size: 0.76rem;
  line-height: 1.45;
}

/* One grid for the whole table, with each row flattened into it: that is what
   makes a chip sit under the same chip on the row above. */
.report__grid {
  display: grid;
  align-items: center;
  gap: 0 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.report__row {
  display: contents;
}

.report__name {
  overflow: hidden;
  padding: 6px 0;
  border-bottom: 1px solid
    color-mix(in srgb, var(--r-color-tooltip-fg) 8%, transparent);
  font-size: 0.79rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report__gap {
  color: var(--r-color-tooltip-fg);
  font-size: 0.74rem;
  opacity: 0.16;
}

.report__cell {
  display: flex;
  padding: 6px 0;
  border-bottom: 1px solid
    color-mix(in srgb, var(--r-color-tooltip-fg) 8%, transparent);
}

/* The last row's cells sit on the tooltip's own edge: no rule under it. */
.report__row:last-child .report__name,
.report__row:last-child .report__cell {
  border-bottom: 0;
}

.report__chip {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 2px 7px;
  border-radius: 7px;
  /* Tinted by the rating's own colour, at a weight that keeps the label legible
     against the tooltip's near-black: the tone reads, the text still reads. */
  background: color-mix(in srgb, currentColor 18%, transparent);
  font-size: 0.74rem;
  line-height: 1.35;
  white-space: nowrap;
}

.report__chip b {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.report__link {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0 -6px -2px;
  padding: 7px 6px 3px;
  border-top: 1px solid
    color-mix(in srgb, var(--r-color-tooltip-fg) 12%, transparent);
  color: var(--r-color-tooltip-fg);
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
}

.report__link:hover {
  color: var(--r-color-tooltip-fg);
  text-decoration: underline;
}

.report__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
}

.report__dot.is-great,
.report__chip.is-great {
  color: #3fbf6f;
}
.report__dot.is-good,
.report__chip.is-good {
  color: #8fd14f;
}
.report__dot.is-mixed,
.report__chip.is-mixed {
  color: #f0c25a;
}
.report__dot.is-bad,
.report__chip.is-bad {
  color: #f2726a;
}

/* The action row's buttons are styled by the shared button's own stylesheet,
   which is scoped to that component and cannot reach a button rendered here.
   What a plugin adds therefore has to paint itself into the same row: the same
   circle, the same glass, the same ladder, or it reads as bare glyphs beside
   RomM's own. */
.r-game-btn--action-plugin {
  appearance: none;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--r-color-border-strong);
  border-radius: 50%;
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
  backdrop-filter: blur(20px);
  cursor: pointer;
  transition:
    background 120ms ease,
    color 120ms ease;
}

.r-game-btn--action-plugin:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}

.r-game-btn--action-plugin.r-game-btn--default {
  width: 40px;
  height: 40px;
}

.r-game-btn--action-plugin.r-game-btn--large {
  width: 44px;
  height: 44px;
}

.r-game-btn--action-plugin.r-game-btn--default .r-icon {
  font-size: 20px;
}

.r-game-btn--action-plugin.r-game-btn--large .r-icon {
  font-size: 22px;
}

.r-game-btn--action-plugin .r-game-btn__img {
  width: 20px;
  height: 20px;
  border-radius: 4px;
}

.plugin-slot__logo {
  width: 18px;
  height: 18px;
  object-fit: contain;
}
</style>
