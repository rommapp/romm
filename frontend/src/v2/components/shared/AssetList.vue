<script setup lang="ts">
// Vertical list for saves, paired with <AssetStrip>. Shared by the launch
// screens (selection) and the Save data subtab (management).
//
// Saves group by slot (archives last), newest version first with the older
// ones folded; a save's screenshot, when it has one, is the row thumbnail.
//
// Two modes, driven by `selectable`:
//   * selectable (default) — Play view. Each row is a button; clicking
//     emits `select`; the chosen row gets a brand rail + a check icon.
//   * manage (selectable=false) — Save data subtab. Rows are static; the
//     trailing area renders the `#actions` slot (download/delete/toggle),
//     and `showOwner` adds an author chip for community items.
import { RBtn, RIcon, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { AUTOSAVE_SLOT } from "@/services/api/save";
import { formatTimestamp } from "@/utils";
import AssetChips from "@/v2/components/shared/AssetChips.vue";
import AssetGroupHead from "@/v2/components/shared/AssetGroupHead.vue";
import AssetOwnerChip from "@/v2/components/shared/AssetOwnerChip.vue";
import AssetTimestamp from "@/v2/components/shared/AssetTimestamp.vue";
import { useGroupFold } from "@/v2/composables/useGroupFold";
import {
  byUpdatedDesc,
  dateOf,
  ownerOf,
  screenshotOf,
  staggerIndex,
  type Asset,
  type AssetDateField,
  type AssetOwner,
  type AssetType,
} from "@/v2/utils/assets";
import { toCssUrl } from "@/v2/utils/css";

defineOptions({ inheritAttrs: false });

interface SlotGroup {
  key: string;
  /** Null for the archive of slot-less saves and for ungrouped states. */
  slot: string | null;
  owner: AssetOwner | null;
  /** Newest first. */
  versions: Asset[];
}

const props = withDefaults(
  defineProps<{
    assets: Asset[];
    type: AssetType;
    /** Play view: rows are selectable buttons with a check. When false,
     *  rows are static and host the `#actions` slot (management). */
    selectable?: boolean;
    selectedId?: number | null;
    /** Render an author chip (avatar + username) for community items. */
    showOwner?: boolean;
    /** Internal max-height + scroll. Off when the parent owns scrolling. */
    scrollable?: boolean;
    /** Which timestamp the rows show. Set it to whatever the caller ordered
     *  the list by, so the newest row is the one that reads newest. */
    timestamp?: AssetDateField;
    /** Off for lists whose saves are not slot versions (stream archives). */
    groupBySlot?: boolean;
  }>(),
  {
    selectable: true,
    selectedId: null,
    showOwner: false,
    scrollable: true,
    timestamp: "updated",
    groupBySlot: true,
  },
);

defineEmits<{
  select: [asset: Asset];
}>();

defineSlots<{
  actions(props: { asset: Asset }): unknown;
}>();

const { t, locale } = useI18n();

const emptyLabel = computed(() =>
  props.type === "save"
    ? t("play.no-saves-available")
    : t("play.no-states-available"),
);

const timeLabel = computed(() =>
  props.timestamp === "created" ? t("rom.created") : t("rom.updated"),
);

function slotOf(asset: Asset): string | null {
  return "slot" in asset && asset.slot ? asset.slot : null;
}

// Only saves have slots; states render as one flat, headerless group.
const grouped = computed(() => props.type === "save" && props.groupBySlot);

// Autosave leads, named slots follow by recency, and the archive closes the
// list. Community lists key by owner too so two users' slots never merge.
const groups = computed<SlotGroup[]>(() => {
  if (!grouped.value) {
    return [{ key: "all", slot: null, owner: null, versions: props.assets }];
  }
  const byKey = new Map<string, SlotGroup>();
  for (const asset of props.assets) {
    const slot = slotOf(asset);
    const key = `${asset.user_id}:${slot ?? ""}`;
    let group = byKey.get(key);
    if (!group) {
      group = { key, slot, owner: ownerOf(asset), versions: [] };
      byKey.set(key, group);
    }
    group.versions.push(asset);
  }
  const rank = (group: SlotGroup) =>
    group.slot === null ? 2 : group.slot === AUTOSAVE_SLOT ? 0 : 1;
  const list = [...byKey.values()];
  for (const group of list) group.versions.sort(byUpdatedDesc);
  return list.sort(
    (a, b) => rank(a) - rank(b) || byUpdatedDesc(a.versions[0], b.versions[0]),
  );
});

// Older versions stay folded until opened or until one of them is selected.
const fold = useGroupFold<SlotGroup>({
  groups,
  keyOf: (group) => group.key,
  holdsSelection: (group) =>
    props.selectable &&
    group.versions.slice(1).some((asset) => asset.id === props.selectedId),
  defaultOpen: () => false,
  selectedId: () => props.selectedId,
});
function isExpanded(group: SlotGroup): boolean {
  return !grouped.value || fold.isOpen(group);
}
function visibleVersions(group: SlotGroup): Asset[] {
  return isExpanded(group) ? group.versions : group.versions.slice(0, 1);
}

const fadeIndex = computed(() =>
  staggerIndex(groups.value.map(visibleVersions)),
);
</script>

<template>
  <div class="r-asset-list" :class="{ 'r-asset-list--scroll': scrollable }">
    <ul v-if="assets.length > 0" class="r-asset-list__groups">
      <li
        v-for="group in groups"
        :key="group.key"
        class="r-asset-list__group"
        :class="{ 'r-asset-list__group--slot': grouped }"
      >
        <AssetGroupHead
          v-if="grouped"
          :icon="
            group.slot ? 'mdi-content-save-all-outline' : 'mdi-archive-outline'
          "
          :icon-tone="group.slot ? 'brand' : 'muted'"
          :title="group.slot ?? t('play.slot-none')"
          :count="t('play.slot-versions', group.versions.length)"
        >
          <AssetOwnerChip
            v-if="showOwner && group.owner"
            :owner="group.owner"
          />
        </AssetGroupHead>

        <ul class="r-asset-list__items">
          <li
            v-for="(asset, i) in visibleVersions(group)"
            :key="asset.id"
            class="r-asset-list__item r-v2-asset-fade"
            :class="{
              'r-asset-list__item--active':
                selectable && asset.id === selectedId,
            }"
            :style="{ '--asset-fade-i': fadeIndex.get(asset.id) }"
          >
            <component
              :is="selectable ? 'button' : 'div'"
              :type="selectable ? 'button' : undefined"
              class="r-asset-list__row"
              :class="{ 'r-asset-list__row--static': !selectable }"
              :aria-pressed="selectable ? asset.id === selectedId : undefined"
              @click="selectable && $emit('select', asset)"
            >
              <span
                class="r-asset-list__icon"
                :class="{ 'r-asset-list__icon--shot': screenshotOf(asset) }"
                :style="
                  screenshotOf(asset)
                    ? { backgroundImage: toCssUrl(screenshotOf(asset)!) }
                    : undefined
                "
                aria-hidden="true"
              >
                <RIcon
                  v-if="!screenshotOf(asset)"
                  :icon="
                    type === 'save' ? 'mdi-content-save' : 'mdi-file-outline'
                  "
                  size="22"
                />
              </span>

              <span class="r-asset-list__main">
                <span class="r-asset-list__name">{{ asset.file_name }}</span>
                <span class="r-asset-list__chips">
                  <AssetOwnerChip
                    v-if="!grouped && showOwner && ownerOf(asset)"
                    :owner="ownerOf(asset)!"
                  />
                  <AssetChips
                    :asset="asset"
                    :latest="grouped && i === 0 && group.versions.length > 1"
                  />
                </span>
              </span>

              <AssetTimestamp
                class="r-asset-list__time"
                :date="dateOf(asset, timestamp)"
                align="end"
              />

              <span
                v-if="selectable"
                class="r-asset-list__check"
                aria-hidden="true"
              >
                <RIcon
                  v-if="asset.id === selectedId"
                  icon="mdi-check-circle"
                  size="18"
                />
              </span>
              <span v-else class="r-asset-list__actions">
                <slot name="actions" :asset="asset" />
              </span>

              <RTooltip
                v-if="selectable"
                activator="parent"
                location="top"
                :open-delay="400"
              >
                <div class="r-asset-list__tip">
                  <span class="r-asset-list__tip-name">
                    {{ asset.file_name }}
                  </span>
                  <span class="r-asset-list__tip-sub">
                    {{ timeLabel }}:
                    {{ formatTimestamp(dateOf(asset, timestamp), locale) }}
                  </span>
                </div>
              </RTooltip>
            </component>
          </li>
        </ul>

        <RBtn
          v-if="grouped && group.versions.length > 1"
          class="r-asset-list__fold"
          variant="text"
          size="x-small"
          :prepend-icon="
            isExpanded(group) ? 'mdi-chevron-up' : 'mdi-chevron-down'
          "
          :aria-expanded="isExpanded(group)"
          @click="fold.toggle(group)"
        >
          {{
            isExpanded(group)
              ? t("play.hide-older-versions")
              : t("play.show-older-versions", group.versions.length - 1)
          }}
        </RBtn>
      </li>
    </ul>

    <div v-else class="r-asset-list__empty">
      <RIcon
        :icon="
          type === 'save' ? 'mdi-content-save-outline' : 'mdi-file-outline'
        "
        size="28"
      />
      <p>{{ emptyLabel }}</p>
    </div>
  </div>
</template>

<style scoped>
.r-asset-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.r-asset-list__groups {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}
/* Internal scroll only where the parent does not own scrolling. The
   vertical padding absorbs the rows' -1px hover lift at the scroll edges. */
.r-asset-list--scroll .r-asset-list__groups {
  overflow-y: auto;
  max-height: 380px;
  padding: 4px 10px 4px 0;
}

.r-asset-list__group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
/* Each slot sits on its own neutral band, so the gaps between sections
   read as separators. */
.r-asset-list__group--slot {
  padding: 6px 8px 8px;
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
}

.r-asset-list__items {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-asset-list__item {
  position: relative;
}

.r-asset-list__row {
  appearance: none;
  border: 1px solid var(--r-color-border);
  background: var(--r-color-bg-elevated);
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--r-radius-md);
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: var(--r-color-fg);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
  position: relative;
  overflow: hidden;
}
.r-asset-list__row:hover {
  border-color: var(--r-color-border-strong);
  background: var(--r-color-surface);
  transform: translateY(-1px);
}
.r-asset-list__item--active .r-asset-list__row {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}
/* Manage mode: rows are static info containers, not selectable buttons.
   No pointer cursor, no hover-lift — only the action buttons react. */
.r-asset-list__row--static {
  cursor: default;
}
.r-asset-list__row--static:hover {
  border-color: var(--r-color-border);
  background: var(--r-color-bg-elevated);
  transform: none;
}

.r-asset-list__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
}
/* A 16:9 thumbnail at the icon's height. */
.r-asset-list__icon--shot {
  width: 64px;
  background-size: cover;
  background-position: center;
}
.r-asset-list__item--active .r-asset-list__icon {
  background-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 22%,
    transparent
  );
  color: var(--r-color-brand-primary);
}

.r-asset-list__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-asset-list__name {
  display: block;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-asset-list__item--active .r-asset-list__name {
  color: var(--r-color-brand-primary);
}
.r-asset-list__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.r-asset-list__check {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  color: var(--r-color-fg-faint);
}
.r-asset-list__item--active .r-asset-list__check {
  color: var(--r-color-brand-primary);
}

/* Manage mode: trailing action buttons (download / delete / toggle). */
.r-asset-list__actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.r-asset-list__fold {
  align-self: flex-start;
}

.r-asset-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 12px;
  color: var(--r-color-fg-muted);
  text-align: center;
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-asset-list__empty p {
  margin: 0;
  font-size: 12px;
}

.r-asset-list__tip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 360px;
}
.r-asset-list__tip-name {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  word-break: break-all;
}
.r-asset-list__tip-sub {
  font-size: 11px;
  opacity: 0.85;
}

html[data-bp~="xs"] .r-asset-list__row {
  padding: 8px 10px;
}
/* Manage mode on phones: the timestamp and actions drop to a row of their
   own under the text, so the name gets the full width and wraps. */
html[data-bp~="xs"] .r-asset-list__row--static {
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas:
    "icon main main"
    ". time actions";
  gap: 4px 10px;
}
html[data-bp~="xs"] .r-asset-list__row--static .r-asset-list__icon {
  grid-area: icon;
  align-self: start;
}
html[data-bp~="xs"] .r-asset-list__row--static .r-asset-list__main {
  grid-area: main;
}
html[data-bp~="xs"] .r-asset-list__row--static .r-asset-list__name {
  white-space: normal;
  overflow-wrap: anywhere;
}
html[data-bp~="xs"] .r-asset-list__row--static .r-asset-list__time {
  grid-area: time;
  align-items: flex-start;
}
html[data-bp~="xs"] .r-asset-list__row--static .r-asset-list__actions {
  grid-area: actions;
  margin-bottom: -4px;
}
</style>
