<script setup lang="ts">
// Each game is either hidden or allowed, so the two lists never overlap.
import { RBtn, RIcon, RSliderBtnGroup, RSpinner, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useDebouncedSearch } from "@/v2/composables/useDebouncedSearch";

defineOptions({ inheritAttrs: false });

defineProps<{ hint?: string }>();
defineSlots<{ label?: () => unknown }>();

const hidden = defineModel<number[]>("hidden", { required: true });
const allowed = defineModel<number[]>("allowed", { required: true });

type Exception = "hide" | "allow";

const { t } = useI18n();

const term = ref<string | null>(null);
const { input: query, setSearch } = useDebouncedSearch(term);
const results = ref<SimpleRom[]>([]);
const fetching = ref(false);
// The spinner covers the debounce wait too, so stale matches don't linger.
const loading = computed(() => {
  const typed = query.value.trim();
  return fetching.value || (!!typed && typed !== (term.value ?? ""));
});
// Full rom objects keyed by id so both the results and the selected list can
// render covers (selected ids hidden in a past session are fetched on demand).
const romCache = ref<Record<number, SimpleRom>>({});

function romName(rom: SimpleRom): string {
  return rom.name || rom.fs_name || `#${rom.id}`;
}

function nameFor(id: number): string {
  const rom = romCache.value[id];
  return rom ? romName(rom) : `#${id}`;
}

let searchToken = 0;

watch(term, async (searchTerm) => {
  const token = ++searchToken;
  if (!searchTerm) {
    results.value = [];
    fetching.value = false;
    return;
  }
  fetching.value = true;
  try {
    const { data } = await romApi.getRoms({ searchTerm, limit: 15 });
    if (token !== searchToken) return;
    results.value = data.items;
    for (const rom of data.items) romCache.value[rom.id] = rom;
  } catch (err) {
    if (token === searchToken) console.error("Game search failed", err);
  } finally {
    if (token === searchToken) fetching.value = false;
  }
});

const pickedIds = computed(() => [...hidden.value, ...allowed.value]);

// Resolve full roms for ids picked earlier so their covers and names render.
watch(
  pickedIds,
  async (ids) => {
    const missing = ids.filter((id) => !(id in romCache.value));
    await Promise.all(
      missing.map(async (id) => {
        try {
          const { data } = await romApi.getRomSimple({ romId: id });
          romCache.value[id] = data;
        } catch {
          /* leave uncached: the row falls back to a placeholder cover */
        }
      }),
    );
  },
  { immediate: true },
);

const selected = computed(() =>
  [
    ...hidden.value.map((id) => ({ id, exception: "hide" as const })),
    ...allowed.value.map((id) => ({ id, exception: "allow" as const })),
  ]
    .map((pick) => ({
      ...pick,
      rom: romCache.value[pick.id] ?? null,
      name: nameFor(pick.id),
    }))
    .sort((a, b) => a.name.localeCompare(b.name)),
);
const addable = computed(() =>
  results.value.filter((rom) => !pickedIds.value.includes(rom.id)),
);

const exceptionItems = computed(() => [
  {
    id: "hide" as const,
    label: t("settings.game-exception-hide"),
    icon: "mdi-eye-off-outline",
  },
  {
    id: "allow" as const,
    label: t("settings.game-exception-allow"),
    icon: "mdi-check-decagram-outline",
  },
]);

// Each list is written once per change, from its current value.
function set(id: number, exception: Exception | null) {
  const keptHidden = hidden.value.filter((x) => x !== id);
  const keptAllowed = allowed.value.filter((x) => x !== id);
  hidden.value = exception === "hide" ? [...keptHidden, id] : keptHidden;
  allowed.value = exception === "allow" ? [...keptAllowed, id] : keptAllowed;
}

function add(rom: SimpleRom, exception: Exception) {
  romCache.value[rom.id] = rom;
  set(rom.id, exception);
  // The results stay open so several games can be added in one go.
}
</script>

<template>
  <div v-bind="$attrs" class="r-v2-gamex">
    <span v-if="$slots.label" class="r-v2-gamex__label">
      <slot name="label" />
    </span>
    <RTextField
      :model-value="query"
      prefix-label="inline"
      density="compact"
      hide-details
      :placeholder="t('settings.game-exceptions-search')"
      @update:model-value="setSearch"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <div v-if="loading" class="r-v2-gamex__status">
      <RSpinner :size="16" />
    </div>
    <ul v-else-if="addable.length" class="r-v2-gamex__results">
      <li v-for="rom in addable" :key="rom.id" class="r-v2-gamex__row">
        <span class="r-v2-gamex__thumb">
          <GameCover :rom="rom" :title="romName(rom)" />
        </span>
        <span class="r-v2-gamex__name">{{ romName(rom) }}</span>
        <RBtn
          v-for="item in exceptionItems"
          :key="item.id"
          variant="text"
          size="small"
          :prepend-icon="item.icon"
          @click="add(rom, item.id)"
        >
          {{ item.label }}
        </RBtn>
      </li>
    </ul>

    <ul v-if="selected.length" class="r-v2-gamex__selected">
      <li v-for="pick in selected" :key="pick.id" class="r-v2-gamex__row">
        <span class="r-v2-gamex__thumb">
          <GameCover :rom="pick.rom" :title="pick.name" />
        </span>
        <span class="r-v2-gamex__name">{{ pick.name }}</span>
        <span class="r-v2-gamex__toggle">
          <RSliderBtnGroup
            :model-value="pick.exception"
            :items="exceptionItems"
            variant="tab"
            size="x-small"
            :aria-label="pick.name"
            @update:model-value="set(pick.id, $event)"
          />
        </span>
        <RBtn
          variant="text"
          icon="mdi-close"
          size="small"
          class="r-v2-gamex__remove"
          :aria-label="t('common.remove')"
          @click="set(pick.id, null)"
        />
      </li>
    </ul>
    <span v-if="hint" class="r-v2-gamex__hint">{{ hint }}</span>
  </div>
</template>

<style scoped>
.r-v2-gamex {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
/* Matches RSelect's stacked label and hint, which a list has no field for. */
.r-v2-gamex__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding-inline-start: 2px;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1.2;
  color: var(--r-color-fg-muted);
}
.r-v2-gamex__hint {
  padding-inline: 4px;
  font-size: 11px;
  line-height: 1.3;
  color: var(--r-color-fg-muted);
}
.r-v2-gamex__status {
  display: flex;
  justify-content: center;
  padding: 8px;
}
.r-v2-gamex__results {
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  overflow: hidden;
  max-height: 240px;
  overflow-y: auto;
}
.r-v2-gamex__selected {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-gamex__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
}
.r-v2-gamex__selected .r-v2-gamex__row {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto auto;
  background: var(--r-color-surface);
}
/* On a phone the toggle takes its own line so the name keeps its width. */
html[data-bp~="xs"] .r-v2-gamex__selected .r-v2-gamex__row {
  grid-template-columns: 30px minmax(0, 1fr) auto;
  grid-template-areas:
    "thumb name remove"
    "thumb toggle toggle";
  row-gap: 6px;
}
html[data-bp~="xs"] .r-v2-gamex__selected .r-v2-gamex__thumb {
  grid-area: thumb;
}
html[data-bp~="xs"] .r-v2-gamex__selected .r-v2-gamex__name {
  grid-area: name;
}
html[data-bp~="xs"] .r-v2-gamex__selected .r-v2-gamex__toggle {
  grid-area: toggle;
}
html[data-bp~="xs"] .r-v2-gamex__selected .r-v2-gamex__remove {
  grid-area: remove;
}
.r-v2-gamex__results .r-v2-gamex__row {
  border-radius: 0;
}
.r-v2-gamex__results li:not(:last-child) {
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-gamex__thumb {
  flex: none;
  width: 30px;
}
.r-v2-gamex__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-gamex__remove {
  flex: none;
}
</style>
