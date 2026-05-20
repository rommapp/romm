<script setup lang="ts">
// PlatformSelect — shared composite that wraps RSelect with the
// platform-row visual language used across v2 (icon + display name,
// optional category / family / missing-fs / rom-count meta).
//
// Consumers own the `items` list — fetch logic stays in stores or the
// call site. Folder mapping passes the full supported-platforms
// catalogue; Scan / FilterDrawer / UploadRomDialog pass DB-existing
// platforms from `storePlatforms`. This component is purely
// presentational + state-shaping.
//
// `showMeta` toggles the Scan-style rich row (category icon, family
// name, missing-fs badge, rom-count tag). Off by default for the
// dialog and filter contexts where the extra columns clutter the
// activator.
//
// Selection / item slots can be overridden when a caller needs to
// drive rendering from external state (FolderMapping reads from `row`
// rather than `items` so the cell still renders during loading or
// when the row points at a slug not in the catalogue).
import { RIcon, RPlatformIcon, RSelect, RTag } from "@v2/lib";
import { computed, useSlots } from "vue";
import type { Platform } from "@/stores/platforms";
import { platformCategoryToIcon } from "@/utils";
import MissingFSBadge from "@/v2/components/shared/MissingFSBadge.vue";

defineOptions({ inheritAttrs: false });

type PlatformKey = "id" | "slug";

interface Props {
  modelValue?: number | string | number[] | string[] | null;
  items: Platform[];
  /** Which Platform field the v-model binds to. Default `id`.
   *  `slug` is used by FolderMapping (the table works in slug space). */
  itemKey?: PlatformKey;
  multiple?: boolean;
  searchable?: boolean;
  clearable?: boolean;
  chips?: boolean;
  closableChips?: boolean;
  disabled?: boolean;
  loading?: boolean;
  label?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  variant?: "outlined" | "filled" | "underlined" | "plain";
  density?: "default" | "comfortable" | "compact";
  hideDetails?: boolean | "auto";
  prefixLabel?: "stacked" | "inline";
  prependInnerIcon?: string;
  /** Scan-style rich row — category icon, family, missing-fs, rom-count. */
  showMeta?: boolean;
  /** Icon size inside list rows. Defaults to 28 (Scan uses 32, dialogs 22-24). */
  iconSize?: number;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  itemKey: "id",
  multiple: false,
  searchable: true,
  clearable: false,
  chips: false,
  closableChips: false,
  disabled: false,
  loading: false,
  label: undefined,
  placeholder: undefined,
  searchPlaceholder: undefined,
  variant: "outlined",
  density: "comfortable",
  hideDetails: "auto",
  prefixLabel: undefined,
  prependInnerIcon: undefined,
  showMeta: false,
  iconSize: 28,
});

const emit = defineEmits<{
  (
    e: "update:modelValue",
    value: number | string | number[] | string[] | null,
  ): void;
}>();

const slots = useSlots();

// Slots we forward verbatim to RSelect. `selection` and `item` are
// handled explicitly above so the caller can choose to override the
// platform-row defaults or use the consumer's template wholesale.
const forwardedSlotNames = computed(() =>
  Object.keys(slots).filter((n) => n !== "selection" && n !== "item"),
);

const platformByKey = computed(() => {
  const m = new Map<number | string, Platform>();
  for (const p of props.items) m.set(p[props.itemKey], p);
  return m;
});

function platformForValue(value: unknown): Platform | undefined {
  if (typeof value !== "number" && typeof value !== "string") return undefined;
  return platformByKey.value.get(value);
}

function onUpdate(v: unknown) {
  emit("update:modelValue", v as number | string | number[] | string[] | null);
}
</script>

<template>
  <RSelect
    v-bind="$attrs"
    :model-value="modelValue"
    :items="items"
    item-title="display_name"
    :item-value="itemKey"
    :multiple="multiple"
    :searchable="searchable"
    :clearable="clearable"
    :chips="chips"
    :closable-chips="closableChips"
    :disabled="disabled"
    :loading="loading"
    :label="label"
    :placeholder="placeholder"
    :search-placeholder="searchPlaceholder"
    :variant="variant"
    :density="density"
    :hide-details="hideDetails"
    :prefix-label="prefixLabel"
    :prepend-inner-icon="prependInnerIcon"
    @update:model-value="onUpdate"
  >
    <!-- Selection — consumer slot wins; otherwise icon + name. -->
    <template #selection="slotProps">
      <slot name="selection" v-bind="slotProps">
        <span class="r-v2-platsel__selection">
          <RPlatformIcon
            v-if="platformForValue(slotProps.item.value)"
            :slug="platformForValue(slotProps.item.value)!.slug"
            :fs-slug="platformForValue(slotProps.item.value)!.fs_slug"
            :name="platformForValue(slotProps.item.value)!.display_name"
            :size="Math.min(iconSize, 24)"
            :show-tooltip="false"
          />
          <span class="r-v2-platsel__name">{{ slotProps.item.title }}</span>
        </span>
      </slot>
    </template>

    <!-- Item — consumer slot wins; otherwise icon + name (+ meta). -->
    <template #item="slotProps">
      <slot name="item" v-bind="slotProps">
        <li v-bind="slotProps.props">
          <RPlatformIcon
            :key="(slotProps.item.raw as Platform).slug"
            :slug="(slotProps.item.raw as Platform).slug"
            :fs-slug="(slotProps.item.raw as Platform).fs_slug"
            :name="(slotProps.item.raw as Platform).display_name"
            :size="iconSize"
            :show-tooltip="false"
          />
          <span class="r-select__item-title">{{ slotProps.item.title }}</span>
          <template v-if="showMeta">
            <span class="r-v2-platsel__meta">
              <RIcon
                v-if="(slotProps.item.raw as Platform).category"
                :icon="
                  platformCategoryToIcon(
                    (slotProps.item.raw as Platform).category || '',
                  )
                "
                size="small"
                class="r-v2-platsel__meta-icon"
              />
              <span
                v-if="(slotProps.item.raw as Platform).family_name"
                class="r-v2-platsel__family"
              >
                {{ (slotProps.item.raw as Platform).family_name }}
              </span>
            </span>
            <MissingFSBadge
              v-if="(slotProps.item.raw as Platform).missing_from_fs"
              text="Missing platform from filesystem"
              class="r-v2-platsel__missing"
            />
            <RTag
              class="r-v2-platsel__count"
              size="small"
              :text="String((slotProps.item.raw as Platform).rom_count)"
            />
          </template>
        </li>
      </slot>
    </template>

    <!-- Forward any other slot the caller passes (prefix-label,
         no-data, details, prepend-inner, append-inner, …). The two
         special slots above are excluded — they have built-in
         defaults and already fall through to the consumer's template
         via the inner `<slot name="…">`. -->
    <template
      v-for="name in forwardedSlotNames"
      :key="name"
      v-slot:[name]="slotProps"
    >
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </RSelect>
</template>

<style scoped>
.r-v2-platsel__selection {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.r-v2-platsel__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-platsel__meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  color: var(--r-color-fg-muted);
}
.r-v2-platsel__meta-icon {
  flex-shrink: 0;
}
.r-v2-platsel__family {
  font-size: 11px;
  white-space: nowrap;
}
.r-v2-platsel__missing {
  margin-left: 4px;
}
.r-v2-platsel__count {
  margin-left: 4px;
}
</style>
