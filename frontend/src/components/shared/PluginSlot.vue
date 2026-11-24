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
          :max-width="340"
          :hint="t('settings.plugins-facts-hint')"
          hint-icon="mdi-open-in-new"
        >
          <div class="plugin-slot__report">
            <p class="plugin-slot__report-head">
              <span
                class="plugin-slot__dot"
                :class="`is-${bestTone(reportFor(action)!)}`"
              />
              <span class="plugin-slot__report-label">{{ action.label }}</span>
              <span
                v-if="reportFor(action)!.total"
                class="plugin-slot__report-total"
                >{{
                  t("settings.plugins-facts-reports", {
                    count: reportFor(action)!.total,
                  })
                }}</span
              >
            </p>

            <p v-if="reportFor(action)!.note" class="plugin-slot__report-note">
              {{ reportFor(action)!.note }}
            </p>

            <ul v-else class="plugin-slot__report-groups">
              <li
                v-for="group in topGroups(reportFor(action)!)"
                :key="group.key"
                class="plugin-slot__report-group"
              >
                <b>{{ group.key }}</b>
                <span
                  v-for="[rating, count] in Object.entries(group.counts ?? {})"
                  :key="rating"
                  class="plugin-slot__rating"
                  :class="`is-${toneFor(rating)}`"
                  >{{ rating }} {{ count }}</span
                >
              </li>
            </ul>
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

/* The tooltip that stands in for the report. It is a small table, so it reads
   in the same order every time: who, then how it rated. */
.plugin-slot__report {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 240px;
}

.plugin-slot__report-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  font-size: 0.85rem;
}

.plugin-slot__report-label {
  font-weight: 600;
}

.plugin-slot__report-total,
.plugin-slot__report-note {
  color: var(--muted-foreground);
  font-size: 0.78rem;
  margin: 0;
}

.plugin-slot__report-total {
  margin-inline-start: auto;
}

.plugin-slot__report-groups {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 0.78rem;
}

.plugin-slot__report-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugin-slot__report-group b {
  min-width: 74px;
  font-weight: 600;
}

.plugin-slot__rating {
  padding: 0 5px;
  border-radius: 5px;
  background: color-mix(in srgb, currentColor 14%, transparent);
}

.plugin-slot__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
  background: currentColor;
}

.plugin-slot__dot.is-great,
.plugin-slot__rating.is-great {
  color: #3fbf6f;
}
.plugin-slot__dot.is-good,
.plugin-slot__rating.is-good {
  color: #8fd14f;
}
.plugin-slot__dot.is-mixed,
.plugin-slot__rating.is-mixed {
  color: #e0b341;
}
.plugin-slot__dot.is-bad,
.plugin-slot__rating.is-bad {
  color: #d9534f;
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
