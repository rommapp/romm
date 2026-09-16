<script setup lang="ts">
// Vertical list for saves, paired with <AssetStrip> (tile grid/strip for
// states). Shared between the EmulatorJS and Stream launch screens
// (selection) and the GameDetails "Save data" subtab (management).
//
// Saves follow the sync clients' slot model: rows group by slot, newest
// version first, with older versions folded behind a toggle. Slot-less saves
// are manual archives and sit in their own group. A save written by the
// browser player carries a screenshot, shown as the row thumbnail.
//
// Two modes, driven by `selectable`:
//   * selectable (default) — Play view. Each row is a button; clicking
//     emits `select`; the chosen row gets a brand rail + a check icon.
//   * manage (selectable=false) — Save data subtab. Rows are static; the
//     trailing area renders the `#actions` slot (download/delete/toggle),
//     and `showOwner` adds an author chip for community items.
import { RAvatar, RBtn, RIcon, RTag, RTooltip } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";
import { AUTOSAVE_SLOT } from "@/services/api/save";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";
import { toCssUrl } from "@/v2/utils/css";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";
type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;
type Owner = UserSaveSchema | UserStateSchema;

interface SlotGroup {
  key: string;
  /** Null for the archive of slot-less saves and for ungrouped states. */
  slot: string | null;
  owner: Owner | null;
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
  }>(),
  {
    selectable: true,
    selectedId: null,
    showOwner: false,
    scrollable: true,
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

function ownerOf(asset: Asset): Owner | null {
  return "username" in asset && asset.username ? asset : null;
}

function screenshotOf(asset: Asset): string | null {
  return asset.screenshot?.download_path ?? null;
}

function slotOf(asset: Asset): string | null {
  return "slot" in asset && asset.slot ? asset.slot : null;
}

// Only saves have slots; states render as one flat, headerless group.
const grouped = computed(() => props.type === "save");

const byUpdatedDesc = (a: Asset, b: Asset) =>
  b.updated_at.localeCompare(a.updated_at);

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

// Keeps the entrance stagger continuous across groups.
const fadeIndex = computed(() => {
  const order = new Map<number, number>();
  for (const group of groups.value) {
    for (const asset of group.versions) order.set(asset.id, order.size);
  }
  return order;
});

// Older versions stay folded unless the user opens them or one is selected.
const expandedKeys = ref(new Set<string>());
function isExpanded(group: SlotGroup): boolean {
  if (!grouped.value || expandedKeys.value.has(group.key)) return true;
  return (
    props.selectable &&
    group.versions.slice(1).some((asset) => asset.id === props.selectedId)
  );
}
function toggleExpanded(group: SlotGroup) {
  const next = new Set(expandedKeys.value);
  if (isExpanded(group)) next.delete(group.key);
  else next.add(group.key);
  expandedKeys.value = next;
}
function visibleVersions(group: SlotGroup): Asset[] {
  return isExpanded(group) ? group.versions : group.versions.slice(0, 1);
}
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
        <div v-if="grouped" class="r-asset-list__group-head">
          <RIcon
            :icon="
              group.slot
                ? 'mdi-content-save-all-outline'
                : 'mdi-archive-outline'
            "
            size="14"
            class="r-asset-list__group-icon"
            :class="{ 'r-asset-list__group-icon--slot': group.slot }"
          />
          <span class="r-asset-list__group-title">
            {{ group.slot ?? t("play.slot-none") }}
          </span>
          <span v-if="showOwner && group.owner" class="r-asset-list__owner">
            <RAvatar
              :image="
                userAvatarUrl({
                  userId: group.owner.user_id,
                  avatarPath: group.owner.user_avatar_path,
                  updatedAt: group.owner.user_updated_at,
                })
              "
              :size="16"
            />
            <span>{{ group.owner.username }}</span>
          </span>
          <span class="r-asset-list__group-count">
            {{ t("play.slot-versions", group.versions.length) }}
          </span>
        </div>

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
                  <span
                    v-if="!grouped && showOwner && ownerOf(asset)"
                    class="r-asset-list__owner"
                  >
                    <RAvatar
                      :image="
                        userAvatarUrl({
                          userId: ownerOf(asset)!.user_id,
                          avatarPath: ownerOf(asset)!.user_avatar_path,
                          updatedAt: ownerOf(asset)!.user_updated_at,
                        })
                      "
                      :size="16"
                    />
                    <span>{{ ownerOf(asset)!.username }}</span>
                  </span>
                  <RTag
                    v-if="grouped && i === 0 && group.versions.length > 1"
                    tone="brand"
                    size="x-small"
                    :text="t('play.latest-version')"
                  />
                  <RTag
                    v-if="asset.emulator"
                    tone="warning"
                    size="x-small"
                    :text="asset.emulator"
                  />
                  <span class="r-asset-list__chip">
                    <RIcon icon="mdi-weight" size="11" />
                    {{ formatBytes(asset.file_size_bytes) }}
                  </span>
                </span>
              </span>

              <span class="r-asset-list__time">
                <span class="r-asset-list__relative">
                  {{ formatRelativeDate(asset.updated_at) }}
                </span>
                <span class="r-asset-list__exact">
                  {{ formatTimestamp(asset.updated_at, locale) }}
                </span>
              </span>

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
                    {{ t("rom.updated") }}:
                    {{ formatTimestamp(asset.updated_at, locale) }}
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
          @click="toggleExpanded(group)"
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
  /* Top padding gives the first row breathing room and absorbs the
     -1px lift on hover/active so it never clips against the panel
     edge. Bottom padding keeps the same gutter at the other end. */
  padding: 4px 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}
/* Internal scroll only where the parent does not own scrolling. */
.r-asset-list--scroll .r-asset-list__groups {
  overflow-y: auto;
  max-height: 380px;
  padding-right: 10px;
}

.r-asset-list__group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* A tinted band, so the slot reads apart from its version rows. */
.r-asset-list__group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--r-radius-sm);
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
  color: var(--r-color-fg-secondary);
}
.r-asset-list__group-icon {
  color: var(--r-color-fg-muted);
}
.r-asset-list__group-icon--slot {
  color: var(--r-color-brand-primary);
}
.r-asset-list__group-title {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-asset-list__group-count {
  margin-left: auto;
  font-size: 10px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
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
.r-asset-list__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 10px;
  color: var(--r-color-fg-secondary);
}
/* Author chip on community rows: avatar + username. */
.r-asset-list__owner {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
}

.r-asset-list__time {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}
.r-asset-list__relative {
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-asset-list__exact {
  font-size: 10px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
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

/* Tighten the row on small screens so the time column doesn't push
   the filename off-screen. The exact timestamp is the first to go —
   the tooltip still has it. */
html[data-bp~="xs"] .r-asset-list__exact {
  display: none;
}
html[data-bp~="xs"] .r-asset-list__row {
  padding: 8px 10px;
}
</style>
