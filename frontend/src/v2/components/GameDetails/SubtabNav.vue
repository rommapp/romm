<script setup lang="ts" generic="T extends string">
// SubtabNav: subtab navigation for the GameDetails tabs that split into
// sections. "list" is a rail beside the content; "menu" is a one-row trigger
// (plus the `actions` slot) opening the list as a bottom sheet on phones.
import { RBtn, RDivider, RIcon, RMenu, RMenuItem } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { shouldAutofocusSearch } from "@/v2/utils/autofocus";

export interface SubtabNavItem<Id extends string = string> {
  id: Id;
  label: string;
  /** Leave unset when every item would carry the same glyph. */
  icon?: string;
  /** Count shown after the label; hidden when zero or unset. */
  badge?: number;
  /** Heading the item is listed under; keep grouped items adjacent. */
  group?: string;
}

// Past this many subtabs the sheet gets a filter field.
const SEARCH_THRESHOLD = 8;

const props = withDefaults(
  defineProps<{
    modelValue: T;
    items: SubtabNavItem<T>[];
    variant?: "list" | "menu";
  }>(),
  { variant: "list" },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: T): void;
}>();

const slots = defineSlots<{
  actions?: () => unknown;
  "item-append"?: (scope: { item: SubtabNavItem<T> }) => unknown;
}>();

const { t } = useI18n();

const active = computed(
  () => props.items.find((item) => item.id === props.modelValue) ?? null,
);

const menuOpen = ref(false);
const search = ref("");
const searchable = computed(() => props.items.length > SEARCH_THRESHOLD);

const menuItems = computed(() => {
  const query = search.value.trim().toLowerCase();
  if (!query) return props.items;
  return props.items.filter((item) => item.label.toLowerCase().includes(query));
});

watch(menuOpen, (open) => {
  if (!open) search.value = "";
});

function startsGroup(list: SubtabNavItem<T>[], index: number): boolean {
  const group = list[index].group;
  return !!group && group !== list[index - 1]?.group;
}

function select(id: T) {
  if (id !== props.modelValue) emit("update:modelValue", id);
}
</script>

<template>
  <ul
    v-if="variant === 'list'"
    class="r-v2-subtab-nav"
    role="tablist"
    aria-orientation="vertical"
  >
    <template v-for="(item, index) in items" :key="item.id">
      <li
        v-if="startsGroup(items, index)"
        role="presentation"
        class="r-v2-subtab-nav__group"
      >
        {{ item.group }}
      </li>
      <li role="presentation" class="r-v2-subtab-nav__item">
        <button
          type="button"
          role="tab"
          class="r-v2-subtab-nav__btn"
          :class="{ 'r-v2-subtab-nav__btn--active': item.id === modelValue }"
          :aria-selected="item.id === modelValue"
          @click="select(item.id)"
        >
          <RIcon v-if="item.icon" :icon="item.icon" size="16" />
          <span class="r-v2-subtab-nav__label">{{ item.label }}</span>
          <slot name="item-append" :item="item" />
          <span v-if="item.badge" class="r-v2-subtab-nav__badge">
            {{ item.badge }}
          </span>
        </button>
      </li>
    </template>
  </ul>

  <!-- Wrapped so call-site classes land on the row rather than on RMenu's
       teleported panel. -->
  <div v-else class="r-v2-subtab-nav-menu">
    <RMenu
      v-model="menuOpen"
      v-model:search="search"
      location="bottom start"
      :offset="6"
      sheet-on-mobile
      :searchable="searchable"
      :search-placeholder="t('common.search')"
      :search-auto-focus="shouldAutofocusSearch()"
    >
      <template #activator="{ props: activatorProps }">
        <RBtn
          v-bind="activatorProps"
          variant="outlined"
          size="small"
          density="comfortable"
          block
          :prepend-icon="active?.icon"
          append-icon="mdi-menu-down"
          class="r-v2-subtab-nav__trigger"
        >
          <span class="r-v2-subtab-nav__label">{{ active?.label }}</span>
          <span v-if="active?.badge" class="r-v2-subtab-nav__badge">
            {{ active.badge }}
          </span>
        </RBtn>
      </template>

      <template v-for="(item, index) in menuItems" :key="item.id">
        <template v-if="startsGroup(menuItems, index)">
          <RDivider v-if="index > 0" />
          <div class="r-v2-subtab-nav__group" data-r-menu-no-close>
            {{ item.group }}
          </div>
        </template>
        <RMenuItem
          :icon="item.icon"
          :label="item.label"
          :variant="item.id === modelValue ? 'active' : 'default'"
          :class="{ 'r-v2-subtab-nav__option--bare': !item.icon }"
          @click="select(item.id)"
        >
          <template v-if="item.badge || slots['item-append']" #append>
            <slot name="item-append" :item="item" />
            <span v-if="item.badge" class="r-v2-subtab-nav__badge">
              {{ item.badge }}
            </span>
          </template>
        </RMenuItem>
      </template>
    </RMenu>
    <slot name="actions" />
  </div>
</template>

<style scoped>
/* ---------- List ----------
   Scrolls on its own when a parent caps its height (FilesTab's folder rail),
   so a ROM with many folders keeps every subtab reachable. */
.r-v2-subtab-nav {
  list-style: none;
  margin: 0;
  padding: 0 4px 4px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-v2-subtab-nav::-webkit-scrollbar {
  width: 4px;
}
.r-v2-subtab-nav::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 2px;
}
.r-v2-subtab-nav__group {
  padding: 8px 12px 4px;
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
.r-v2-subtab-nav__item {
  display: flex;
  flex-direction: column;
}
.r-v2-subtab-nav__btn {
  width: 100%;
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-muted);
  font-family: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-subtab-nav__btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-subtab-nav__btn--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
}
/* The list is a scroll container that clips the global outline ring, so paint
   the key / pad focus inside the button instead. */
html:not([data-input]) .r-v2-subtab-nav__btn:focus-visible,
html[data-input="key"] .r-v2-subtab-nav__btn:focus-visible,
html[data-input="pad"] .r-v2-subtab-nav__btn:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px var(--r-color-focus);
}
.r-v2-subtab-nav__label {
  flex: 1;
}
.r-v2-subtab-nav__badge {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  padding: 1px 7px;
  border-radius: var(--r-radius-full);
  background: color-mix(in srgb, currentColor 18%, transparent);
}

/* RMenuItem keeps an icon cell even when empty; drop it so icon-less rows
   line up with their group heading. */
.r-v2-subtab-nav__option--bare :deep(.r-menu-item__icon) {
  display: none;
}

/* ---------- Menu trigger ----------
   Reads as a select: active subtab on the left, chevron pinned right. */
.r-v2-subtab-nav-menu {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.r-v2-subtab-nav__trigger {
  flex: 1;
  min-width: 0;
}
.r-v2-subtab-nav__trigger :deep(.r-btn__content),
.r-v2-subtab-nav__trigger :deep(.r-btn__label) {
  flex: 1;
  min-width: 0;
}
.r-v2-subtab-nav__trigger .r-v2-subtab-nav__label {
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}
</style>
