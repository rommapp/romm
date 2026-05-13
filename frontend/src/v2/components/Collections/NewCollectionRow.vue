<script setup lang="ts">
// NewCollectionRow — the "create collection" CTA row inside the
// AddRomsToCollectionDialog. Collapsed: purple-tinted plus-tile + label.
// Expanded: inline name input with Create / Cancel actions.
//
// Stateless — the parent owns `expanded`, `name`, and `creating`. The
// `+` tile and row frame are shared between the two states so the
// expand animation reads as the same surface swapping its contents.
import { RBtn, RIcon } from "@v2/lib";
import { computed, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

interface Props {
  expanded: boolean;
  name: string;
  creating: boolean;
  // Tile diameter in px. Drives both the grid first-column width and the
  // plus-tile width so the prepended slot stays flush with the label
  // column regardless of size. Match the row's CollectionMosaic thumb.
  tileSize?: number;
}

const props = withDefaults(defineProps<Props>(), {
  tileSize: 36,
});

const rowStyle = computed(() => ({
  "--tile-w": `${props.tileSize}px`,
}));

const emit = defineEmits<{
  (e: "update:expanded", value: boolean): void;
  (e: "update:name", value: string): void;
  (e: "create"): void;
  (e: "cancel"): void;
}>();

const { t } = useI18n();

const input = ref<HTMLInputElement | null>(null);

watch(
  () => props.expanded,
  (expanded) => {
    if (expanded) nextTick(() => input.value?.focus());
  },
);

function onExpand() {
  emit("update:expanded", true);
}
function onCancel() {
  emit("cancel");
}
function onSubmit() {
  emit("create");
}
function onInput(e: Event) {
  emit("update:name", (e.target as HTMLInputElement).value);
}
</script>

<template>
  <button
    v-if="!expanded"
    type="button"
    class="new-row"
    :style="rowStyle"
    @click="onExpand"
  >
    <span class="new-row__tile">
      <RIcon icon="mdi-plus" size="22" />
    </span>
    <span class="new-row__label">
      {{ t("collection.new-collection", "New Collection") }}
    </span>
  </button>
  <form
    v-else
    class="new-row new-row--editing"
    :style="rowStyle"
    @submit.prevent="onSubmit"
  >
    <span class="new-row__tile new-row__tile--active">
      <RIcon icon="mdi-plus" size="22" />
    </span>
    <input
      ref="input"
      :value="name"
      type="text"
      class="new-row__input"
      :placeholder="
        t('collection.collection-name-placeholder', 'Collection name')
      "
      :disabled="creating"
      :aria-label="t('collection.new-collection', 'New Collection')"
      @input="onInput"
      @keydown.esc.prevent="onCancel"
    />
    <div class="new-row__actions">
      <RBtn
        variant="text"
        size="small"
        :disabled="creating"
        @click.prevent="onCancel"
      >
        {{ t("common.cancel") }}
      </RBtn>
      <RBtn
        variant="translucent"
        color="primary"
        size="small"
        type="submit"
        :disabled="!name.trim() || creating"
        :loading="creating"
      >
        {{ t("common.create", "Create") }}
      </RBtn>
    </div>
  </form>
</template>

<style scoped>
/* Negative horizontal margin compensates for the RDialog body padding
   so the CTA stretches edge-to-edge, matching the picker rows below. */
.new-row {
  appearance: none;
  display: grid;
  /* First column tracks the configurable tile width so the label always
     starts past the tile, even when the consumer makes the tile bigger. */
  grid-template-columns: var(--tile-w, 36px) 1fr auto;
  align-items: center;
  gap: 14px;
  width: calc(100% + 36px);
  margin: -18px -18px 0;
  padding: 10px 30px;
  background: transparent;
  border: 0;
  cursor: pointer;
  color: inherit;
  font-family: inherit;
  text-align: left;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.new-row:hover {
  background: var(--r-color-bg-elevated);
}
.new-row--editing {
  cursor: default;
  background: color-mix(in srgb, var(--r-color-brand-primary) 5%, transparent);
}

/* Portrait plus-tile — matches the CollectionMosaic footprint of the
   picker rows so the first column aligns whether you're looking at the
   CTA or an existing collection thumb. */
.new-row__tile {
  width: var(--tile-w, 36px);
  aspect-ratio: 140 / 188;
  border-radius: 6px;
  border: 1px solid var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 16%, transparent);
  color: var(--r-color-brand-primary);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.new-row:hover .new-row__tile,
.new-row__tile--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 28%, transparent);
  color: var(--r-color-overlay-fg);
}

.new-row__label {
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
}

.new-row__input {
  appearance: none;
  background: transparent;
  border: 0;
  color: var(--r-color-fg);
  font-size: 14px;
  font-family: inherit;
  font-weight: var(--r-font-weight-medium);
  padding: 8px 0;
  outline: none;
  min-width: 0;
}
.new-row__input::placeholder {
  color: var(--r-color-fg-faint);
  font-weight: var(--r-font-weight-regular);
}

.new-row__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

:global(.r-v2.r-v2-light) .new-row:hover {
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
}
:global(.r-v2.r-v2-light) .new-row__input::placeholder {
  color: color-mix(in srgb, var(--r-color-fg) 35%, transparent);
}
</style>
