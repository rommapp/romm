<script setup lang="ts">
// NewCollectionRow — the "create collection" CTA row inside the
// ManageCollectionsDialog. Collapsed: purple-tinted plus-tile + label.
// Expanded: inline name input with Create / Cancel actions.
//
// Stateless — the parent owns `expanded`, `name`, and `creating`. The
// outer row + tile are persistent across both states so the background
// tint and tile-active swap transition smoothly instead of remounting;
// only the middle (label vs input) and the trailing actions toggle.
import { RBtn, RIcon } from "@v2/lib";
import { computed, nextTick, ref, useId, watch } from "vue";
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

// Stable id so the trailing Create button (sibling of the form) can
// submit via the `form` HTML attribute. Lets the actions live outside
// the form node so their Vue Transition can run a clean leave when the
// row collapses.
const formId = useId();

watch(
  () => props.expanded,
  (expanded) => {
    if (expanded) nextTick(() => input.value?.focus());
  },
);

function onRowClick() {
  // Tile / empty-row clicks expand the row when collapsed. The inner
  // label-button and input swallow their own clicks, so this only
  // triggers for the row's chrome.
  if (!props.expanded) emit("update:expanded", true);
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
  <div
    class="new-row"
    :class="{ 'new-row--editing': expanded }"
    :style="rowStyle"
    @click="onRowClick"
  >
    <span class="new-row__tile" :class="{ 'new-row__tile--active': expanded }">
      <RIcon icon="mdi-plus" size="22" />
    </span>

    <!-- Middle column: label (collapsed) or input (expanded). The swap
         is instant; the surrounding row stays mounted so the tile and
         background transition smoothly instead of unmounting. -->
    <button
      v-if="!expanded"
      type="button"
      class="new-row__cta"
      @click.stop="emit('update:expanded', true)"
    >
      {{ t("collection.new-collection", "New Collection") }}
    </button>
    <form
      v-else
      :id="formId"
      class="new-row__form"
      @submit.prevent="onSubmit"
      @click.stop
    >
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
    </form>

    <!-- Actions sit outside the form (Create wires via `form` attr) so
         their Vue Transition can run a clean enter+leave when the row
         expands/collapses without the form's unmount cutting it short. -->
    <Transition name="new-row-actions">
      <div v-if="expanded" class="new-row__actions" @click.stop>
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
          :form="formId"
          :disabled="!name.trim() || creating"
          :loading="creating"
        >
          {{ t("common.create", "Create") }}
        </RBtn>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Negative horizontal margin compensates for the RDialog body padding
   so the CTA stretches edge-to-edge, matching the picker rows below. */
.new-row {
  display: grid;
  /* First column tracks the configurable tile width so the label always
     starts past the tile, even when the consumer makes the tile bigger.
     Third column is `auto` — sizes to the actions when present, collapses
     to 0 when the Transition unmounts them. */
  grid-template-columns: var(--tile-w, 36px) 1fr auto;
  align-items: center;
  gap: 14px;
  width: calc(100% + 36px);
  margin: -18px -18px 0;
  padding: 10px 30px;
  background: transparent;
  cursor: pointer;
  color: inherit;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.new-row:not(.new-row--editing):hover {
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
.new-row:not(.new-row--editing):hover .new-row__tile,
.new-row__tile--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 28%, transparent);
  color: var(--r-color-overlay-fg);
}

/* Label-as-button — left-aligned, no chrome so it reads as a row label
   that happens to be focusable. */
.new-row__cta {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  font-family: inherit;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  text-align: left;
  cursor: pointer;
}

.new-row__form {
  display: flex;
  min-width: 0;
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
  width: 100%;
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

:global(.r-v2.r-v2-light) .new-row:not(.new-row--editing):hover {
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
}
:global(.r-v2.r-v2-light) .new-row__input::placeholder {
  color: color-mix(in srgb, var(--r-color-fg) 35%, transparent);
}

/* Cancel/Create transition — slides in from the right on expand and
   slides back out on cancel. Both directions animate because the
   actions cluster lives outside the form, so its Vue Transition leave
   isn't cut short by a form unmount. */
.new-row-actions-enter-active,
.new-row-actions-leave-active {
  transition:
    opacity 180ms var(--r-motion-ease-out),
    transform 180ms var(--r-motion-ease-out);
}
.new-row-actions-enter-from,
.new-row-actions-leave-to {
  opacity: 0;
  transform: translateX(8px);
}
</style>
