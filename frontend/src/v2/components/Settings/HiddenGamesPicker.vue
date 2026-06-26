<script setup lang="ts">
// HiddenGamesPicker — search the library and pick individual games to hide
// from a user. Model is the list of hidden rom ids. A debounced search shows
// matching games (cover + name); picked games render below as a removable
// list (cover + name), with their full rom cached so covers resolve even for
// ids that were hidden before this session.
import { RBtn, RIcon, RSpinner, RTextField } from "@v2/lib";
import { debounce } from "lodash";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import GameCover from "@/v2/components/shared/GameCover.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ modelValue: number[] }>();
const emit = defineEmits<{ "update:modelValue": [number[]] }>();

const { t } = useI18n();

const query = ref("");
const results = ref<SimpleRom[]>([]);
const loading = ref(false);
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

const runSearch = debounce(async (term: string) => {
  if (!term.trim()) {
    results.value = [];
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    const { data } = await romApi.getRoms({ searchTerm: term, limit: 15 });
    results.value = data.items;
    for (const rom of data.items) romCache.value[rom.id] = rom;
  } catch (err) {
    console.error("Game search failed", err);
  } finally {
    loading.value = false;
  }
}, 300);

watch(query, (q) => {
  loading.value = !!q.trim();
  runSearch(q);
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
          /* leave uncached — the row falls back to a placeholder cover */
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
  // Keep the results open so several games can be added in one go — the added
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
  <div class="r-v2-hgames">
    <RTextField
      v-model="query"
      prefix-label="inline"
      density="compact"
      hide-details
      :placeholder="t('settings.hidden-games-search')"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <div v-if="loading" class="r-v2-hgames__status">
      <RSpinner :size="16" />
    </div>
    <ul v-else-if="addable.length" class="r-v2-hgames__results">
      <li v-for="rom in addable" :key="rom.id">
        <button
          type="button"
          class="r-v2-hgames__row r-v2-hgames__row--add"
          @click="add(rom)"
        >
          <span class="r-v2-hgames__thumb">
            <GameCover :rom="rom" :title="romName(rom)" />
          </span>
          <span class="r-v2-hgames__name">{{ romName(rom) }}</span>
          <RIcon icon="mdi-plus" size="18" class="r-v2-hgames__add-icon" />
        </button>
      </li>
    </ul>

    <ul v-if="selected.length" class="r-v2-hgames__selected">
      <li v-for="s in selected" :key="s.id" class="r-v2-hgames__row">
        <span class="r-v2-hgames__thumb">
          <GameCover :rom="s.rom" :title="s.name" />
        </span>
        <span class="r-v2-hgames__name">{{ s.name }}</span>
        <RBtn
          variant="text"
          icon="mdi-close"
          size="small"
          class="r-v2-hgames__remove"
          :aria-label="t('common.remove')"
          @click="remove(s.id)"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.r-v2-hgames {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-hgames__status {
  display: flex;
  justify-content: center;
  padding: 8px;
}
.r-v2-hgames__results {
  border: 1px solid var(--r-color-border);
  border-radius: 8px;
  overflow: hidden;
  max-height: 240px;
  overflow-y: auto;
}
.r-v2-hgames__selected {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-hgames__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
}
.r-v2-hgames__selected .r-v2-hgames__row {
  background: var(--r-color-surface);
}
.r-v2-hgames__row--add {
  cursor: pointer;
  /* Native <button> reset so it reads as a plain row. */
  width: 100%;
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  text-align: left;
}
.r-v2-hgames__row--add:hover {
  background: var(--r-color-surface);
}
.r-v2-hgames__results li:not(:last-child) {
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-hgames__thumb {
  flex: none;
  width: 30px;
}
.r-v2-hgames__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-hgames__add-icon {
  flex: none;
  color: var(--r-color-fg-muted);
}
.r-v2-hgames__remove {
  flex: none;
}
</style>
