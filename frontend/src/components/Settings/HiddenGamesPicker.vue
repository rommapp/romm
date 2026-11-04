<script setup lang="ts">
// HiddenGamesPicker: search the library and pick individual games to hide
// from a user. Model is the list of hidden rom ids. A debounced search shows
// matching games (cover + name); picked games render below as a removable
// list (cover + name), with their full rom cached so covers resolve even for
// ids that were hidden before this session.
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import GameCover from "@/components/shared/GameCover.vue";
import { useDebouncedSearch } from "@/composables/useDebouncedSearch";
import { RBtn, RIcon, RSpinner, RTextField } from "@/lib";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ modelValue: number[] }>();
const emit = defineEmits<{ "update:modelValue": [number[]] }>();

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

// Resolve full roms for already-hidden ids so their covers and names render.
watch(
  () => props.modelValue,
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
  props.modelValue.map((id) => ({
    id,
    rom: romCache.value[id] ?? null,
    name: nameFor(id),
  })),
);
const addable = computed(() =>
  results.value.filter((rom) => !props.modelValue.includes(rom.id)),
);

function add(rom: SimpleRom) {
  if (!props.modelValue.includes(rom.id)) {
    romCache.value[rom.id] = rom;
    emit("update:modelValue", [...props.modelValue, rom.id]);
  }
  // Keep the results open so several games can be added in one go: the added
  // rom drops out of `addable`, the rest of the matches stay visible.
}

function remove(id: number) {
  emit(
    "update:modelValue",
    props.modelValue.filter((x) => x !== id),
  );
}
</script>

<template>
  <div class="r-hgames">
    <RTextField
      :model-value="query"
      prefix-label="inline"
      density="compact"
      hide-details
      :placeholder="t('settings.hidden-games-search')"
      @update:model-value="setSearch"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <div v-if="loading" class="r-hgames__status">
      <RSpinner :size="16" />
    </div>
    <ul v-else-if="addable.length" class="r-hgames__results">
      <li v-for="rom in addable" :key="rom.id">
        <button
          type="button"
          class="r-hgames__row r-hgames__row--add"
          @click="add(rom)"
        >
          <span class="r-hgames__thumb">
            <GameCover :rom="rom" :title="romName(rom)" responsive />
          </span>
          <span class="r-hgames__name">{{ romName(rom) }}</span>
          <RIcon icon="mdi-plus" size="18" class="r-hgames__add-icon" />
        </button>
      </li>
    </ul>

    <ul v-if="selected.length" class="r-hgames__selected">
      <li v-for="s in selected" :key="s.id" class="r-hgames__row">
        <span class="r-hgames__thumb">
          <GameCover :rom="s.rom" :title="s.name" responsive />
        </span>
        <span class="r-hgames__name">{{ s.name }}</span>
        <RBtn
          variant="text"
          icon="mdi-close"
          size="small"
          class="r-hgames__remove"
          :aria-label="t('common.remove')"
          @click="remove(s.id)"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.r-hgames {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-hgames__status {
  display: flex;
  justify-content: center;
  padding: 8px;
}
.r-hgames__results {
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  overflow: hidden;
  max-height: 240px;
  overflow-y: auto;
}
.r-hgames__selected {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-hgames__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
}
.r-hgames__selected .r-hgames__row {
  background: var(--r-color-surface);
}
.r-hgames__row--add {
  cursor: pointer;
  /* Native <button> reset so it reads as a plain row. */
  width: 100%;
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  text-align: left;
}
.r-hgames__row--add:hover {
  background: var(--r-color-surface);
}
.r-hgames__results li:not(:last-child) {
  border-bottom: 1px solid var(--r-color-border);
}
.r-hgames__thumb {
  flex: none;
  width: 30px;
}
.r-hgames__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-hgames__add-icon {
  flex: none;
  color: var(--r-color-fg-muted);
}
.r-hgames__remove {
  flex: none;
}
</style>
