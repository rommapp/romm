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
import { RAvatar, RIcon, RPlatformIcon, RSelect, RTag } from "@v2/lib";
import { computed, useSlots } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import { platformCategoryToIcon } from "@/utils";
import MissingFSBadge from "@/v2/components/shared/MissingFSBadge.vue";

// Per-platform scrapper match indicators — mini avatar per metadata
// source the platform has an ID for. Mixed `_id` / `_slug` fields
// because the PlatformSchema only exposes one of the two per source
// (e.g. moby is keyed by slug, igdb by both). Keep in sync with v1's
// platform-row template and the heartbeat store's source list.
const PLATFORM_SCRAPPERS: ReadonlyArray<{
  key: keyof Platform;
  logo: string;
  name: string;
  bg?: string;
}> = [
  { key: "igdb_id", logo: "/assets/scrappers/igdb.png", name: "IGDB" },
  { key: "ss_id", logo: "/assets/scrappers/ss.png", name: "ScreenScraper" },
  { key: "moby_slug", logo: "/assets/scrappers/moby.png", name: "MobyGames" },
  { key: "ra_id", logo: "/assets/scrappers/ra.png", name: "RetroAchievements" },
  {
    key: "launchbox_id",
    logo: "/assets/scrappers/launchbox.png",
    name: "LaunchBox",
    bg: "#185a7c",
  },
  {
    key: "hasheous_id",
    logo: "/assets/scrappers/hasheous.png",
    name: "Hasheous",
  },
  {
    key: "flashpoint_id",
    logo: "/assets/scrappers/flashpoint.png",
    name: "Flashpoint",
  },
  {
    key: "hltb_slug",
    logo: "/assets/scrappers/hltb.png",
    name: "HowLongToBeat",
  },
  {
    key: "libretro_slug",
    logo: "/assets/scrappers/libretro.png",
    name: "Libretro",
  },
];

function activeScrappers(p: Platform) {
  return PLATFORM_SCRAPPERS.filter((s) => Boolean(p[s.key]));
}

defineOptions({ inheritAttrs: false });

type PlatformKey = "id" | "slug" | "fs_slug";

interface Props {
  modelValue?: number | string | number[] | string[] | null;
  items: Platform[];
  /** Which Platform field the v-model binds to. Default `id`.
   *  `slug` is used by FolderMapping (the table works in slug space)
   *  `fs_slug` is used by Scan (mixes database platforms and folders) */
  itemKey?: PlatformKey;
  multiple?: boolean;
  searchable?: boolean;
  clearable?: boolean;
  /** When `multiple`, render each selection as a small icon-only RTag
   *  with an automatic "+N" overflow pill. Defaults to `true` so the
   *  visual is consistent across every multi-platform picker; pass
   *  `:chips="false"` for the comma-separated title fallback. */
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
  /** Never-scanned folders. */
  markUnscanned?: boolean;
  /** Label for the never-scanned marker */
  unscannedLabel?: string;
  /** Icon size inside list rows. Defaults to 28 (Scan uses 32, dialogs 22-24). */
  iconSize?: number;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  itemKey: "id",
  multiple: false,
  searchable: true,
  clearable: false,
  chips: true,
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
  markUnscanned: false,
  unscannedLabel: undefined,
  iconSize: 28,
});

const emit = defineEmits<{
  (
    e: "update:modelValue",
    value: number | string | number[] | string[] | null,
  ): void;
}>();

const { t } = useI18n();
const slots = useSlots();

// Slots we forward verbatim to RSelect. `selection`, `item`, and
// `chip` are handled explicitly above so the caller can choose to
// override the platform-row defaults or use the consumer's template
// wholesale.
const forwardedSlotNames = computed(() =>
  Object.keys(slots).filter(
    (n) => n !== "selection" && n !== "item" && n !== "chip",
  ),
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
    chip-tone="plain"
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

    <!-- Chip — when `chips` is on (multi-select) the activator
         collapses each selection into a small RTag. PlatformSelect
         renders just the platform icon inside the chip; RSelect
         keeps providing the "+N" overflow pill automatically. The
         tooltip on RPlatformIcon serves the same role the title
         text used to (hover the chip → see the platform name). -->
    <template #chip="slotProps">
      <slot name="chip" v-bind="slotProps">
        <RPlatformIcon
          v-if="platformForValue(slotProps.item.value)"
          :slug="platformForValue(slotProps.item.value)!.slug"
          :fs-slug="platformForValue(slotProps.item.value)!.fs_slug"
          :name="platformForValue(slotProps.item.value)!.display_name"
          :title="platformForValue(slotProps.item.value)!.display_name"
          :size="18"
          class="r-v2-platsel__chip-icon"
        />
        <span v-else>{{ slotProps.item.title }}</span>
      </slot>
    </template>

    <!-- Item — consumer slot wins; otherwise icon + name (+ meta). -->
    <template #item="slotProps">
      <slot name="item" v-bind="slotProps">
        <li v-bind="slotProps.props" class="r-v2-platsel__row">
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
              <RTag
                size="x-small"
                class="r-v2-platsel__fs-slug"
                :text="(slotProps.item.raw as Platform).fs_slug"
              />
              <RTag
                v-if="
                  markUnscanned &&
                  unscannedLabel &&
                  (slotProps.item.raw as Platform).id < 0
                "
                size="x-small"
                tone="info"
                prepend-icon="mdi-folder-plus-outline"
                class="r-v2-platsel__unscanned"
                :text="unscannedLabel"
              />
              <RIcon
                v-if="(slotProps.item.raw as Platform).category"
                :icon="
                  platformCategoryToIcon(
                    (slotProps.item.raw as Platform).category || '',
                  )
                "
                size="small"
                class="r-v2-platsel__meta-icon"
                :title="(slotProps.item.raw as Platform).category || ''"
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
              :text="t('rom.missing-platform')"
              class="r-v2-platsel__missing"
            />
            <!-- Scrapper match indicators — one mini avatar per
                 source the platform has an ID for. Mirrors v1's
                 right-side avatar strip so the user sees at a glance
                 which catalogs already know this platform. When the
                 platform isn't matched at all, a red "Not identified"
                 chip replaces the strip. -->
            <span
              v-if="(slotProps.item.raw as Platform).is_identified"
              class="r-v2-platsel__scrappers"
            >
              <RAvatar
                v-for="s in activeScrappers(slotProps.item.raw as Platform)"
                :key="s.key as string"
                :image="s.logo"
                size="20"
                rounded="sm"
                :title="s.name"
                :style="s.bg ? { background: s.bg } : undefined"
                class="r-v2-platsel__scrapper"
              />
            </span>
            <RTag
              v-else
              size="x-small"
              tone="danger"
              icon="mdi-close"
              class="r-v2-platsel__not-identified"
              :text="t('scan.not-identified').toUpperCase()"
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
.r-v2-platsel__row {
  container-name: r-v2-platsel__row;
  container-type: inline-size;
}
.r-v2-platsel__meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  color: var(--r-color-fg-muted);
}

/* Narrow: shed the low-priority descriptors. */
@container r-v2-platsel__row (max-width: 560px) {
  .r-v2-platsel__fs-slug,
  .r-v2-platsel__family,
  .r-v2-platsel__meta-icon {
    display: none;
  }
}
/* Narrower still: drop the scrapper match strip too. */
@container r-v2-platsel__row (max-width: 400px) {
  .r-v2-platsel__scrappers {
    display: none;
  }
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
.r-v2-platsel__fs-slug {
  font-family: var(--r-font-family-mono);
  font-size: 10.5px;
  text-transform: lowercase;
}
.r-v2-platsel__unscanned {
  flex-shrink: 0;
}
.r-v2-platsel__scrappers {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 4px;
}
.r-v2-platsel__scrapper {
  background: var(--r-color-surface);
  flex-shrink: 0;
}
.r-v2-platsel__not-identified {
  margin-left: 4px;
}
.r-v2-platsel__chip-icon {
  display: inline-flex;
  align-items: center;
}
</style>
