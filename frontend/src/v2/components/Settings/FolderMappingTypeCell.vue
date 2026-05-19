<script setup lang="ts">
// FolderMappingTypeCell — editable Type cell (alias / variant) for the
// folder mappings table.
//
// Implementation: a plain `RSelect` with two options. Conceptually
// this is "pick one", same as PlatformCell — a select reads more
// honestly than a button-activated menu and keeps the visual
// vocabulary identical across the table.
//
// Editability matches v1: any row with a slug (alias / variant /
// auto) can be retyped. Auto rows are listed as the current value
// but the items array doesn't include "auto", so the dropdown only
// ever exposes the two user-selectable options (alias, variant).
// Unmapped rows (no slug) stay non-editable — the user picks a
// platform first via FolderMappingPlatformCell, which lands the row
// as `alias` by default.
//
// The selected-value text picks up a colour token per type
// (`brand-primary` / `accent` / `success`) so the cell still reads
// at a glance as alias / variant / auto. Read-only fallback renders
// an RTag with the same tone vocabulary.
import { RIcon, RSelect, RTag } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

type RowType = "alias" | "variant" | "auto" | null;

interface TypeItem {
  value: "alias" | "variant";
  title: string;
  icon: string;
}

interface Props {
  row: { fsSlug: string; slug?: string; displayName?: string; type: RowType };
  canEdit: boolean;
}
const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "select", type: "alias" | "variant"): void;
}>();

const { t } = useI18n();

const items = computed<TypeItem[]>(() => [
  {
    value: "alias",
    title: t("settings.folder-alias"),
    icon: "mdi-label-variant",
  },
  {
    value: "variant",
    title: t("settings.platform-variant"),
    icon: "mdi-source-branch",
  },
]);

// Pass `row.type` straight through — even when it's `auto` (a value
// not in `items`). VSelect will fall back to rendering the
// `#selection` slot with `item.raw = "auto"`; we ignore the slot's
// `item` and paint `label` ourselves, so the "auto-detected" pill
// shows up regardless. Masking auto to `null` would silently drop
// the slot call and leave the cell empty (only the chevron visible).
const modelType = computed({
  get: () => props.row.type,
  set: (next) => {
    if (next === "alias" || next === "variant") emit("select", next);
  },
});

const isEditable = computed(() => props.canEdit && !!props.row.slug);

type RTagTone = "brand" | "accent" | "success";
const tagTone = computed<RTagTone>(() => {
  if (props.row.type === "alias") return "brand";
  if (props.row.type === "variant") return "accent";
  return "success";
});

const label = computed(() => {
  if (props.row.type === "alias") return t("settings.folder-alias");
  if (props.row.type === "variant") return t("settings.platform-variant");
  return t("settings.auto-detected");
});
</script>

<template>
  <RSelect
    v-if="isEditable"
    v-model="modelType"
    :items="items"
    item-title="title"
    item-value="value"
    hide-details
    density="compact"
    variant="plain"
    class="r-v2-fmtc"
    :class="`r-v2-fmtc--${row.type ?? 'unset'}`"
  >
    <!-- Auto rows aren't in the items list, so VSelect's default
         selection rendering would show empty — paint the current
         label manually here. -->
    <template #selection>
      <RTag :tone="tagTone" :text="label" size="small" />
    </template>
    <template #item="{ props: itemProps, item }">
      <li
        v-bind="itemProps"
        :class="`r-v2-fmtc-item--${(item.raw as TypeItem).value}`"
      >
        <RIcon :icon="(item.raw as TypeItem).icon" size="16" />
        <span class="r-select__item-title">
          {{ (item.raw as TypeItem).title }}
        </span>
      </li>
    </template>
  </RSelect>
  <RTag v-else-if="row.type" :tone="tagTone" :text="label" size="x-small" />
</template>

<style scoped>
/* Tint the selection text by current type — keeps the at-a-glance
   colour cue we had with the chip-style button while letting the
   field do all the heavy lifting. */
.r-v2-fmtc__label {
  font-weight: var(--r-font-weight-medium);
}
.r-v2-fmtc--alias .r-v2-fmtc__label {
  color: var(--r-color-brand-primary);
}
.r-v2-fmtc--variant .r-v2-fmtc__label {
  color: var(--r-color-brand-accent);
}
.r-v2-fmtc--auto .r-v2-fmtc__label {
  color: var(--r-color-success);
}
</style>

<!-- Dropdown items live in `.r-select__menu`, teleported outside the
     scoped subtree. Colour them in an unscoped block so the same
     brand/accent/success vocabulary the field uses extends into the
     menu — picking "Folder alias" reads as purple in the dropdown
     too, "Platform variant" as orange, etc. -->
<style>
.r-select__menu .r-v2-fmtc-item--alias {
  color: var(--r-color-brand-primary) !important;
}
.r-select__menu .r-v2-fmtc-item--variant {
  color: var(--r-color-brand-accent) !important;
}
</style>
