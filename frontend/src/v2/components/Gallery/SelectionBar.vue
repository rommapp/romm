<script setup lang="ts">
// SelectionBar — floating bottom panel that surfaces bulk actions
// over the currently-selected ROMs. Replaces v1's `FabOverlay`
// speed-dial: the bar sits below the gallery, never inside the
// toolbar, so filter/search/sort all stay reachable while the user
// is selecting (vs. v1's behaviour of co-opting the toolbar).
//
// Visibility: bound to `gallerySelection.enabled`. Slides up from
// `bottom: 0` when the first ROM is selected and slides back down
// when the count drops to zero — the panel stays mounted so its
// buttons keep their ripple state cleanly between cycles.
//
// Actions wire-up:
//   * favorite / unfavorite — direct collectionApi bulk call against
//     the favorite collection. The Card/Row's per-rom favourite
//     toggle still routes through `useGameActions` per-rom; here we
//     bypass it to issue a single add/remove call for the whole set.
//   * manage collections — re-uses the existing
//     `ManageCollectionsDialog` (already accepts SimpleRom[]) via
//     the `showManageCollectionsDialog` emitter event.
//   * download — a single selected ROM downloads directly (like the
//     per-rom `useGameActions.download`); multi-selections go through
//     the bulk endpoint so the server bundles them into one zip.
//   * refresh metadata — emits `showRefreshMetadataDialog` for each
//     ROM in turn. (Phase-2 follow-up: the dialog will accept arrays
//     so the user only sees the scan-type picker once for the whole
//     batch instead of N dialogs.)
//   * delete — emits `showDeleteRomDialog` with the full selection;
//     the dialog already paints a per-ROM "remove from disk"
//     checklist for bulk deletes.
//
// Permissions: scan and delete are gated by `useCan` so users
// without `rom.refresh` / `rom.delete` don't see actions they can't
// run.
import {
  RBtn,
  RIcon,
  RMenu,
  RMenuItem,
  RToolbar,
  RTooltip,
  RDivider,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject } from "vue";
import { useI18n } from "vue-i18n";
import type { RomUserData, RomUserStatus } from "@/__generated__";
import collectionApi from "@/services/api/collection";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { romStatusMap } from "@/utils";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import {
  ENUM_KEYS,
  FLAG_KEYS,
  PLAY_FLAG_KEYS,
  STATUS_ICONS,
  type StatusFlagKey,
  VISIBILITY_FLAG_KEYS,
} from "@/v2/utils/romStatus";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
// On phones the bar drops the "N selected" phrase down to just the
// number so the action row fits a 320px width without overflowing.
const { xs } = useBreakpoint();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const selection = storeGallerySelection();
const collectionsStore = storeCollections();
const romsStore = storeRoms();

const canRefresh = useCan("rom.refresh");
const canDelete = useCan("rom.delete");
const canDownload = useCan("rom.download");

// `favorite` is the favourite collection — used to compute "are all
// selected ROMs in favorites?" so the button can toggle between
// "add to" / "remove from" instead of forcing a separate unfavorite
// action. Same model as the per-card favourite button.
const allFavorited = computed(() => {
  const fav = collectionsStore.favoriteCollection;
  if (!fav || selection.count === 0) return false;
  const favIds = new Set(fav.rom_ids ?? []);
  for (const id of selection.ids) {
    if (!favIds.has(id)) return false;
  }
  return true;
});

const favoriteIcon = computed(() =>
  allFavorited.value ? "mdi-heart" : "mdi-heart-outline",
);
const favoriteLabel = computed(() =>
  allFavorited.value
    ? t("gallery.selection-unfavorite")
    : t("gallery.selection-favorite"),
);

async function bulkFavorite() {
  const fav = collectionsStore.favoriteCollection;
  const ids = selection.ids;
  if (!fav || ids.length === 0) return;
  try {
    const { data } = allFavorited.value
      ? await collectionApi.removeRomsFromCollection(fav.id, ids)
      : await collectionApi.addRomsToCollection(fav.id, ids);
    collectionsStore.updateCollection(data);
    collectionsStore.setFavoriteCollection(data);
    if (allFavorited.value && romsStore.currentCollection?.id === fav.id) {
      // We were on the favourites collection view and just removed
      // every selected rom from it — drop them from the visible
      // roms so the UI reflects the new membership immediately.
      romsStore.remove(selection.roms);
    }
    snackbar.success(
      allFavorited.value
        ? t("gallery.selection-unfavorite-success", { n: ids.length })
        : t("gallery.selection-favorite-success", { n: ids.length }),
    );
  } catch {
    snackbar.error(t("gallery.selection-favorite-fail"));
  }
}

// Bulk status — toggles one play-status across the whole selection,
// mirroring the favourite button's all-or-nothing model: a status reads
// as "active" only when *every* selected ROM already has it. Clicking an
// active status clears it on all; clicking an inactive one (at least one
// ROM is missing it) sets it on all. The per-rom `updateUserRomProps` is
// the only endpoint (no bulk variant), so we fan out one request per ROM,
// optimistically write the store, and revert only the ROMs whose request
// failed.
//
// `enumAllActive` / `flagAllActive` mirror `allFavorited`: keyed by
// status so each menu row can paint its active state and decide its
// toggle direction.
const enumAllActive = computed<Record<RomUserStatus, boolean>>(() => {
  const roms = selection.roms;
  const out = {} as Record<RomUserStatus, boolean>;
  for (const key of ENUM_KEYS) {
    out[key] = roms.length > 0 && roms.every((r) => r.rom_user?.status === key);
  }
  return out;
});
const flagAllActive = computed<Record<StatusFlagKey, boolean>>(() => {
  const roms = selection.roms;
  const out = {} as Record<StatusFlagKey, boolean>;
  for (const key of FLAG_KEYS) {
    out[key] = roms.length > 0 && roms.every((r) => Boolean(r.rom_user?.[key]));
  }
  return out;
});
const hasAnyStatus = computed(() => {
  const roms = selection.roms;
  return roms.some(
    (r) =>
      Boolean(r.rom_user?.status) ||
      FLAG_KEYS.some((key) => Boolean(r.rom_user?.[key])),
  );
});

async function applyStatus(data: Partial<RomUserData>) {
  const roms = selection.roms;
  if (roms.length === 0) return;

  const before = new Map<number, RomUserData>();
  for (const rom of roms) {
    if (!rom.rom_user) continue;
    before.set(rom.id, { ...rom.rom_user });
    Object.assign(rom.rom_user, data);
    romsStore.update(rom);
  }

  const results = await Promise.allSettled(
    roms.map((rom) => romApi.updateUserRomProps({ romId: rom.id, data })),
  );
  const failed = roms.filter((_, i) => results[i].status === "rejected");
  for (const rom of failed) {
    const snapshot = before.get(rom.id);
    if (rom.rom_user && snapshot) {
      Object.assign(rom.rom_user, snapshot);
      romsStore.update(rom);
    }
  }

  const ok = roms.length - failed.length;
  if (failed.length === 0) {
    snackbar.success(t("gallery.selection-status-success", { n: ok }));
  } else if (ok > 0) {
    snackbar.warning(
      t("gallery.selection-status-partial", { n: ok, total: roms.length }),
    );
  } else {
    snackbar.error(t("gallery.selection-status-fail"));
  }
}

function toggleEnumStatus(key: RomUserStatus) {
  void applyStatus({ status: enumAllActive.value[key] ? null : key });
}

function toggleFlagStatus(key: StatusFlagKey) {
  void applyStatus({ [key]: !flagAllActive.value[key] });
}

function clearStatus() {
  void applyStatus({
    now_playing: false,
    backlogged: false,
    hidden: false,
    status: null,
  });
}

function manageCollections() {
  if (selection.count === 0) return;
  emitter?.emit("showManageCollectionsDialog", selection.roms);
}

function bulkDownload() {
  const roms = selection.roms;
  if (roms.length === 0) return;
  if (roms.length === 1) {
    void romApi.downloadRom({ rom: roms[0] });
    return;
  }
  // Bundle multi-selections into a single zip server-side; firing one
  // anchor download per ROM trips browser multi-download blocking.
  void romApi.bulkDownloadRoms({ roms });
  snackbar.info(t("gallery.selection-download-many", { n: roms.length }));
}

function bulkRefresh() {
  if (selection.count === 0) return;
  // The v2 dialog listens to both single + bulk events; v1 only sees
  // the single one. Emitting the bulk variant keeps the v1 dialog
  // (still mounted under uiVersion === "v1") out of this flow.
  emitter?.emit("showRefreshMetadataDialogBulk", selection.roms);
}

function bulkDelete() {
  if (selection.count === 0) return;
  emitter?.emit("showDeleteRomDialog", selection.roms);
}

function clear() {
  selection.clear();
}
</script>

<template>
  <div
    class="selection-bar"
    :class="{ 'selection-bar--visible': selection.enabled }"
    :aria-hidden="!selection.enabled"
  >
    <RToolbar
      density="compact"
      rounded="full"
      flat
      class="selection-bar__panel"
    >
      <!-- Prepend region: count chip — leftmost item, separated from
           the action buttons by RToolbar's built-in inter-region
           spacing. -->
      <template #prepend>
        <div class="selection-bar__count">
          <RIcon
            icon="mdi-check-circle"
            size="18"
            class="selection-bar__count-icon"
          />
          <span>
            <template v-if="xs">{{ selection.count }}</template>
            <template v-else>
              {{ t("gallery.selection-n-selected", { n: selection.count }) }}
            </template>
          </span>
        </div>
      </template>

      <RDivider vertical class="selection-bar__divider" />

      <!-- Default slot: action buttons. Order mirrors the v1 FAB:
           download → favourite → collections → refresh → delete.
           Every button is wrapped in RTooltip so the user gets a
           consistent hover hint and gamepad users see the label —
           the v2 visual vocabulary for icon-only buttons. -->
      <RTooltip v-if="canDownload" :text="t('gallery.selection-download')">
        <template #activator="{ props: tipProps }">
          <RBtn
            v-bind="tipProps"
            icon="mdi-download"
            variant="text"
            :aria-label="t('gallery.selection-download')"
            @click="bulkDownload"
          />
        </template>
      </RTooltip>

      <RTooltip :text="favoriteLabel">
        <template #activator="{ props: tipProps }">
          <RBtn
            v-bind="tipProps"
            :icon="favoriteIcon"
            variant="text"
            :color="allFavorited ? 'primary' : undefined"
            :aria-label="favoriteLabel"
            @click="bulkFavorite"
          />
        </template>
      </RTooltip>

      <!-- Set status — opens a picker that toggles one play-status across
           the whole selection. Mirrors the per-ROM status menu
           (GameActionBtn) and the favourite button's all-or-nothing
           model: a row reads active only when every selected ROM already
           has it; clicking flips it on (if any is missing it) or off (if
           all have it). Stays open on click so the active marks update
           live. Opens upward (location="top") to clear the bottom-
           anchored bar. -->
      <RMenu
        location="top"
        :offset="8"
        width="240px"
        :close-on-content-click="false"
      >
        <template #activator="{ props: activatorProps }">
          <RBtn
            v-bind="activatorProps"
            icon="mdi-list-status"
            variant="text"
            :tooltip="t('gallery.selection-status')"
            :aria-label="t('gallery.selection-status')"
          />
        </template>
        <!-- Enum statuses — single play-status per ROM. Active row tints
             brand when all selected share it. -->
        <RMenuItem
          v-for="key in ENUM_KEYS"
          :key="key"
          :icon="STATUS_ICONS[key]"
          :variant="enumAllActive[key] ? 'active' : 'default'"
          @click="toggleEnumStatus(key)"
        >
          {{ t(romStatusMap[key].i18nKey) }}
        </RMenuItem>

        <RDivider />

        <!-- Play-status flags — independent toggles. Active rows tint
             brand and show a trailing check when every selected ROM has
             the flag set. -->
        <RMenuItem
          v-for="key in PLAY_FLAG_KEYS"
          :key="key"
          :icon="STATUS_ICONS[key]"
          :text-color="flagAllActive[key] ? 'brand-primary' : undefined"
          :icon-color="flagAllActive[key] ? 'brand-primary' : undefined"
          @click="toggleFlagStatus(key)"
        >
          {{ t(romStatusMap[key].i18nKey) }}
          <template v-if="flagAllActive[key]" #append>
            <RIcon icon="mdi-check" size="x-small" color="primary" />
          </template>
        </RMenuItem>

        <RDivider />

        <!-- Visibility flag — distinct category (library visibility,
             not play state) so it lives in its own section. -->
        <RMenuItem
          v-for="key in VISIBILITY_FLAG_KEYS"
          :key="key"
          :icon="STATUS_ICONS[key]"
          :text-color="flagAllActive[key] ? 'brand-primary' : undefined"
          :icon-color="flagAllActive[key] ? 'brand-primary' : undefined"
          @click="toggleFlagStatus(key)"
        >
          {{ t(romStatusMap[key].i18nKey) }}
          <template v-if="flagAllActive[key]" #append>
            <RIcon icon="mdi-check" size="x-small" color="primary" />
          </template>
        </RMenuItem>

        <template v-if="hasAnyStatus">
          <RDivider />
          <RMenuItem
            icon="mdi-close-circle-outline"
            variant="danger"
            @click="clearStatus"
          >
            {{ t("rom.clear-all") }}
          </RMenuItem>
        </template>
      </RMenu>

      <RTooltip :text="t('gallery.selection-collections')">
        <template #activator="{ props: tipProps }">
          <RBtn
            v-bind="tipProps"
            icon="mdi-bookmark-outline"
            variant="text"
            :aria-label="t('gallery.selection-collections')"
            @click="manageCollections"
          />
        </template>
      </RTooltip>

      <RTooltip
        v-if="canRefresh"
        :text="t('gallery.selection-refresh-metadata')"
      >
        <template #activator="{ props: tipProps }">
          <RBtn
            v-bind="tipProps"
            icon="mdi-refresh"
            variant="text"
            :aria-label="t('gallery.selection-refresh-metadata')"
            @click="bulkRefresh"
          />
        </template>
      </RTooltip>

      <RTooltip v-if="canDelete" :text="t('gallery.selection-delete')">
        <template #activator="{ props: tipProps }">
          <RBtn
            v-bind="tipProps"
            icon="mdi-delete-outline"
            variant="text"
            color="danger"
            :aria-label="t('gallery.selection-delete')"
            @click="bulkDelete"
          />
        </template>
      </RTooltip>

      <!-- Append region: clear button — floats to the right edge via
           RToolbar's built-in spacer. -->
      <template #append>
        <RTooltip :text="t('gallery.selection-clear')">
          <template #activator="{ props: tipProps }">
            <RBtn
              v-bind="tipProps"
              icon="mdi-close"
              variant="text"
              :aria-label="t('gallery.selection-clear')"
              @click="clear"
            />
          </template>
        </RTooltip>
      </template>
    </RToolbar>
  </div>
</template>

<style scoped>
.selection-bar {
  position: fixed;
  left: 50%;
  bottom: max(24px, env(safe-area-inset-bottom, 0));
  transform: translate(-50%, calc(100% + 32px));
  /* Above the bottom tab bar (z 100) so the multi-select bar floats over
     it on mobile instead of being painted behind it; still below dialogs
     (z 2400) so a confirm opened from a selection covers it. */
  z-index: 101;
  pointer-events: none;
  transition: transform var(--r-motion-mid) var(--r-motion-ease-out);
  /* Respect the platform's reduced-motion preference: skip the
     slide-up so the bar appears instantly without animation. */
  @media (prefers-reduced-motion: reduce) {
    transition: none;
  }
}

.selection-bar--visible {
  transform: translate(-50%, 0);
  pointer-events: auto;
}

/* On sm-and-down sit just above the bottom tab bar (8px gap) so the two
   read as stacked, not overlapping. Anchoring `bottom` this high means
   the base hide transform (translateY(100% + 32px)) can't clear the
   viewport, so the hidden transform is enlarged to push the panel fully
   past the bar + screen edge; the visible state (declared after, same
   specificity) pins it back at the 8px gap. */
html[data-bp~="sm-and-down"] .selection-bar {
  bottom: calc(var(--r-bottom-nav-h) + 8px + env(safe-area-inset-bottom));
  transform: translate(-50%, calc(100% + var(--r-bottom-nav-h) + 48px));
}
html[data-bp~="sm-and-down"] .selection-bar--visible {
  transform: translate(-50%, 0);
}

/* RToolbar's default surface (`--r-color-bg-elevated`) is overridden
   to the panel glass tone so the bar reads as a sibling of menus /
   dialogs (premise III.1: one visual vocabulary for every surface).
   Border + shadow + backdrop-blur are stacked on top of the
   primitive's flat pill. `max-width` keeps it inside a 320px viewport. */
.selection-bar__panel {
  --r-toolbar-color: var(--r-color-panel);
  max-width: calc(100vw - 16px);
  border: 1px solid var(--r-color-panel-border);
  box-shadow:
    0 12px 32px color-mix(in srgb, black 32%, transparent),
    0 0 0 1px color-mix(in srgb, white 4%, transparent) inset;
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
}

.selection-bar__count {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
}

.selection-bar__count-icon {
  color: var(--r-color-brand-primary);
}

html[data-bp~="xs"] .selection-bar__count {
  padding: 0 2px;
  font-size: var(--r-font-size-sm);
}

/* Tighten the action row on phones so all buttons + the count + divider
   fit a 320px width: squeeze the inter-button gaps and side padding. */
html[data-bp~="xs"] .selection-bar__panel {
  gap: 2px;
  padding: 0 6px;
}
</style>
