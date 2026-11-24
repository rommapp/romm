<script setup lang="ts">
// PluginFacts: what a plugin learned about this game from its own source.
//
// A plugin declares a panel — a name, a source, and the two fields to count by —
// and the server does the reading, because a manifest cannot be trusted with the
// network. This draws what came back: one row per panel, one chip per thing the
// reports were grouped by, and the counts inside each chip. When there is
// nothing to draw it says why rather than leaving a gap.
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { PluginFactSchema } from "@/__generated__";
import { RIcon } from "@/lib";
import pluginApi from "@/services/api/plugin";
import { usePluginStore } from "@/stores/plugins";
import type { SimpleRom } from "@/stores/roms";

const props = defineProps<{
  rom: SimpleRom;
  slot?: string;
}>();

const { t } = useI18n();
const store = usePluginStore();

const facts = ref<PluginFactSchema[]>([]);
const loading = ref(false);
const loadedFor = ref<number | null>(null);

const surface = computed(() => props.slot ?? "game.details");

/** The plugins that fill panels for this surface. */
const sources = computed(() =>
  store.plugins.filter((plugin) =>
    (plugin.facts ?? []).some((fact) => fact.slot === surface.value),
  ),
);

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

function countsOf(fact: PluginFactSchema): [string, number][] {
  const totals = new Map<string, number>();
  for (const group of fact.groups ?? []) {
    for (const [rating, count] of Object.entries(group.counts ?? {})) {
      totals.set(rating, (totals.get(rating) ?? 0) + count);
    }
  }
  return [...totals.entries()].sort((a, b) => b[1] - a[1]);
}

function bestTone(fact: PluginFactSchema): string {
  const counts = countsOf(fact);
  if (!counts.length) return "bad";
  const [rating] = counts.reduce((best, entry) =>
    entry[1] > best[1] ? entry : best,
  );
  return toneFor(rating);
}

async function load(): Promise<void> {
  const romId = props.rom?.id;
  if (!romId || !sources.value.length) {
    facts.value = [];
    loadedFor.value = null;
    return;
  }
  if (loadedFor.value === romId) return;
  loading.value = true;
  const collected: PluginFactSchema[] = [];
  for (const plugin of sources.value) {
    try {
      const reply = await pluginApi.getFacts(plugin.id, romId);
      for (const fact of reply.data?.facts ?? []) {
        if (fact.slot === surface.value) collected.push(fact);
      }
    } catch {
      // A plugin that cannot answer is not worth an error of its own: the rest
      // of the page still works, and its absence is the message.
    }
  }
  facts.value = collected;
  loadedFor.value = romId;
  loading.value = false;
}

watch(
  () => [props.rom?.id, sources.value.length],
  () => void load(),
  { immediate: true },
);
</script>

<template>
  <section
    v-if="loading || facts.length"
    class="plugin-facts"
    :aria-busy="loading"
  >
    <p v-if="loading && !facts.length" class="plugin-facts__note">
      {{ t("settings.plugins-facts-loading") }}
    </p>

    <article v-for="fact in facts" :key="fact.id" class="plugin-facts__panel">
      <header class="plugin-facts__head">
        <span class="plugin-facts__dot" :class="`is-${bestTone(fact)}`" />
        <h3 class="plugin-facts__label">{{ fact.label }}</h3>
        <span v-if="fact.total" class="plugin-facts__total">
          {{
            t("settings.plugins-facts-reports", {
              count: fact.total,
            })
          }}
        </span>
        <a
          v-if="fact.link"
          class="plugin-facts__link"
          :href="fact.link"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ t("settings.plugins-facts-all") }}
          <RIcon icon="mdi-open-in-new" size="12" />
        </a>
      </header>

      <p v-if="fact.note" class="plugin-facts__note">{{ fact.note }}</p>

      <ul v-else class="plugin-facts__groups">
        <li
          v-for="group in fact.groups"
          :key="group.key"
          class="plugin-facts__group"
        >
          <span class="plugin-facts__group-name">{{ group.key }}</span>
          <span
            v-for="[rating, count] in Object.entries(group.counts ?? {})"
            :key="rating"
            class="plugin-facts__rating"
            :class="`is-${toneFor(rating)}`"
          >
            {{ rating }} {{ count }}
          </span>
        </li>
      </ul>
    </article>
  </section>
</template>

<style scoped>
.plugin-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}

.plugin-facts__panel {
  flex: 1 1 320px;
  min-width: 260px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
}

.plugin-facts__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugin-facts__label {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
}

.plugin-facts__total,
.plugin-facts__note {
  color: var(--muted-foreground);
  font-size: 0.78rem;
}

.plugin-facts__link {
  margin-inline-start: auto;
  color: var(--muted-foreground);
  font-size: 0.78rem;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.plugin-facts__link:hover {
  color: var(--foreground);
}

.plugin-facts__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.plugin-facts__groups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.plugin-facts__group {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
}

.plugin-facts__group-name {
  font-weight: 600;
}

.plugin-facts__rating {
  padding: 1px 6px;
  border-radius: 6px;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

.is-great {
  color: #3fbf6f;
  background: #3fbf6f;
}

.plugin-facts__rating.is-great,
.plugin-facts__rating.is-good,
.plugin-facts__rating.is-mixed,
.plugin-facts__rating.is-bad {
  background: color-mix(in srgb, currentColor 14%, transparent);
}

.is-good {
  color: #8fd14f;
}

.is-mixed {
  color: #e0b341;
}

.is-bad {
  color: #d9534f;
}
</style>
