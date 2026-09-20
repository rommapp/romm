<script setup lang="ts" generic="K extends string">
// ListSortMenu: the sort control a list header shows once its columns are
// gone (phones and tablets). Shared by the gallery, platforms and collections
// headers, so the three can't answer "what is this sorted by" three ways.
import { RIcon, RMenu, RMenuItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  options: readonly { key: K; label: string }[];
  /** Null when the list's order is one the columns don't carry. */
  sortKey: K | null;
  sortDir: "asc" | "desc";
}>();

const emit = defineEmits<{
  (e: "sort", payload: { key: K; dir: "asc" | "desc" }): void;
}>();

const { t } = useI18n();
const dirIcon = computed(() =>
  props.sortDir === "asc" ? "mdi-arrow-up-thin" : "mdi-arrow-down-thin",
);
// Naming a column the list isn't sorted by would claim a sort that isn't in
// effect, so an unknown key falls back to the control's own name.
const label = computed(
  () =>
    props.options.find((option) => option.key === props.sortKey)?.label ??
    t("gallery.sort-by"),
);

function pick(key: K) {
  // Toggle direction when re-picking the active key; otherwise start the new
  // one ascending, like every other sortable table in the app.
  const dir: "asc" | "desc" =
    props.sortKey === key && props.sortDir === "asc" ? "desc" : "asc";
  emit("sort", { key, dir });
}
</script>

<template>
  <RMenu location="bottom start" :offset="6" sheet-on-mobile>
    <template #activator="{ props: activatorProps }">
      <button v-bind="activatorProps" type="button" class="list-sort-menu">
        <span class="list-sort-menu__label">{{ label }}</span>
        <RIcon :icon="dirIcon" size="14" class="list-sort-menu__icon" />
      </button>
    </template>
    <RMenuItem
      v-for="option in options"
      :key="option.key"
      :label="option.label"
      :variant="sortKey === option.key ? 'active' : 'default'"
      @click="pick(option.key)"
    >
      <template #append>
        <RIcon
          v-if="sortKey === option.key"
          :icon="dirIcon"
          size="14"
          class="list-sort-menu__icon"
        />
      </template>
    </RMenuItem>
  </RMenu>
</template>

<style scoped>
/* Matches the column-header cells it replaces: same uppercase micro-label,
   same active tone, same brand-tinted direction glyph. */
.list-sort-menu {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--r-color-fg);
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-1);
  min-width: 0;
  height: 100%;
  cursor: pointer;
  text-align: start;
  border-radius: var(--r-radius-sm);
}

.list-sort-menu__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.list-sort-menu__icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}
</style>
