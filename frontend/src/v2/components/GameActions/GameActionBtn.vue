<script setup lang="ts">
// GameActionBtn — single icon button for the per-ROM action set
// shared between the GameCard hover overlay and the GameDetails
// header. One component, three sizes, auto-wires to `useGameActions`
// so both surfaces stay in sync.
//
// Actions:
//   play        → router.push /rom/:id/ejs
//   download    → direct download link click
//   copy-link   → copy the API download URL to clipboard; falls back to
//                 a dialog that shows the link when clipboard is denied
//   qr          → emit showQRCodeDialog (only meaningful for NDS today)
//   favorite    → toggleFavorite; active state when `isFavorited`
//   collection  → open ManageCollectionsDialog; hidden if no collections
//   status      → open status-enum picker (RMenu); icon swaps to the
//                 current status icon when set, dashed border when empty
//   more        → open MoreMenu (GameActionsList dropdown)
//
// Sizes (controls diameter + icon size + padding) — same vocabulary as
// RBtn / RChip / RTag:
//   x-small → 22px
//   small   → 28px — GameCard hover overlay
//   default → 40px — GameDetails header
//   large   → 44px — larger emphasis (GameActions row)
//   x-large → 52px
//
// Variants:
//   glass      → default translucent frosted-glass pill
//   surface    → translucent grey, page-background friendly (Details)
//   emphasized → white-on-dark (used by Play in card + details)
//
// `withLabel` turns the button into a pill with "Play" / "Download" /
// etc. text next to the icon, matching the GameDetails Play CTA.
import { RDivider, RIcon, RMenu, RMenuItem } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref, toRef } from "vue";
import type { RomUserStatus } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { romStatusMap } from "@/utils";
import type { PlayingStatus } from "@/utils";
import GameActionsList from "@/v2/components/GameActions/GameActionsList.vue";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

export type GameAction =
  | "play"
  | "download"
  | "copy-link"
  | "qr"
  | "favorite"
  | "collection"
  | "status"
  | "more";

interface Props {
  rom: SimpleRom;
  action: GameAction;
  /** Size ladder shared with RBtn / RChip / RTag. */
  size?: "x-small" | "small" | "default" | "large" | "x-large";
  /**
   * `glass` — dark scrim, designed to read on top of cover art
   *           (GameCard hover overlay).
   * `surface` — translucent grey surface, matches RTag tokens
   *             (GameDetails header where the buttons sit on the
   *             page background, not over a cover).
   * `emphasized` — primary white-on-dark CTA (Play).
   */
  variant?: "glass" | "surface" | "emphasized";
  withLabel?: boolean;
  /**
   * Status-only: when several status states are active, the button
   * stretches to show every icon. `horizontal` lays them in a row
   * (ribbon), `vertical` stacks them (GameCard top-left badge).
   */
  orientation?: "horizontal" | "vertical";
}

const props = withDefaults(defineProps<Props>(), {
  size: "default",
  variant: "glass",
  withLabel: false,
  orientation: "horizontal",
});

const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);

// Icon map for the status menu — covers both the enum statuses and the
// orthogonal boolean flags (now_playing / backlogged / hidden) so the
// menu can present them as a single surface. Local map so v1 (which
// still consumes `romStatusMap`'s emoji) stays untouched.
// `mdi-progress-helper` is the dashed-circle "no status set yet" icon.
const STATUS_ICONS: Record<PlayingStatus, string> = {
  incomplete: "mdi-progress-clock",
  finished: "mdi-flag-checkered",
  completed_100: "mdi-trophy-outline",
  retired: "mdi-flag-off-outline",
  never_playing: "mdi-cancel",
  now_playing: "mdi-gamepad-variant",
  backlogged: "mdi-clock-outline",
  hidden: "mdi-eye-off-outline",
};
const STATUS_EMPTY_ICON = "mdi-progress-helper";
const ENUM_KEYS: RomUserStatus[] = [
  "incomplete",
  "finished",
  "completed_100",
  "retired",
  "never_playing",
];
type FlagKey = "now_playing" | "backlogged" | "hidden";
// Two groups: play-status flags (now_playing / backlogged) describe
// when the user intends to play; the visibility flag (hidden) controls
// whether the ROM shows up in the library at all. Different category,
// so they get their own divider in the status menu.
const PLAY_FLAG_KEYS: FlagKey[] = ["now_playing", "backlogged"];
const VISIBILITY_FLAG_KEYS: FlagKey[] = ["hidden"];
const FLAG_KEYS: FlagKey[] = [...PLAY_FLAG_KEYS, ...VISIBILITY_FLAG_KEYS];

const enumStatus = computed<RomUserStatus | null>(
  () => props.rom.rom_user?.status ?? null,
);
function isFlagActive(key: FlagKey) {
  return Boolean(props.rom.rom_user?.[key]);
}
// Ordered list of icons for every active status state. Enum first
// (single radio-like pick), then flags in their declared order. Drives
// both the activator (single icon vs multi-icon stretch pill) and the
// counter on the multi-state label.
const activeStatusIcons = computed<string[]>(() => {
  const out: string[] = [];
  if (enumStatus.value) out.push(STATUS_ICONS[enumStatus.value]);
  for (const f of FLAG_KEYS) if (isFlagActive(f)) out.push(STATUS_ICONS[f]);
  return out;
});
const hasAnyStatus = computed(() => activeStatusIcons.value.length > 0);

type Preset = {
  icon: string;
  label: string;
  activeIcon: string | null;
  onClick: (() => void) | null;
  active: boolean;
};

// Presentation metadata per action — icon swaps when active, different
// aria labels, different click handlers. Written as an if-chain instead
// of a switch so the linter can see every path returns.
const preset = computed<Preset>(() => {
  if (props.action === "play") {
    return {
      icon: "mdi-play",
      label: "Play",
      activeIcon: null,
      onClick: actions.play,
      active: false,
    };
  }
  if (props.action === "download") {
    return {
      icon: "mdi-download-outline",
      label: "Download",
      activeIcon: null,
      onClick: actions.download,
      active: false,
    };
  }
  if (props.action === "copy-link") {
    return {
      icon: "mdi-share-variant-outline",
      label: "Copy download link",
      activeIcon: null,
      onClick: actions.copyDownloadLink,
      active: false,
    };
  }
  if (props.action === "qr") {
    return {
      icon: "mdi-qrcode",
      label: "Share (QR code)",
      activeIcon: null,
      onClick: actions.shareQR,
      active: false,
    };
  }
  if (props.action === "favorite") {
    return {
      icon: "mdi-heart-outline",
      activeIcon: "mdi-heart",
      label: actions.isFavorited.value ? "Remove favorite" : "Favorite",
      onClick: actions.favorite,
      active: actions.isFavorited.value,
    };
  }
  if (props.action === "collection") {
    return {
      icon: "mdi-bookmark-outline",
      activeIcon: null,
      label: "Manage collections",
      onClick: actions.manageCollections,
      active: false,
    };
  }
  if (props.action === "status") {
    // Headline:
    //   0 active → dashed "set status" placeholder
    //   1 active → that state's own icon
    //   ≥2 active → activator stretches and renders every icon in
    //              `activeStatusIcons` (the template branches on length).
    const count = activeStatusIcons.value.length;
    const hk = actions.currentStatusKey.value;
    let icon: string;
    let label: string;
    if (count === 0) {
      icon = STATUS_EMPTY_ICON;
      label = "Set status";
    } else if (count === 1 && hk) {
      icon = STATUS_ICONS[hk];
      label = `Status: ${romStatusMap[hk].text}`;
    } else {
      // Multi: template renders the icon stack instead of preset.icon.
      icon = activeStatusIcons.value[0] ?? STATUS_EMPTY_ICON;
      label = `Status: ${count} active`;
    }
    return {
      icon,
      activeIcon: null,
      label,
      onClick: null, // menu owns the click
      active: count > 0,
    };
  }
  // "more" — the RMenu owns activation; no direct click handler.
  return {
    icon: "mdi-dots-horizontal",
    activeIcon: null,
    label: "More actions",
    onClick: null,
    active: false,
  };
});

const displayedIcon = computed(
  () => (preset.value.active && preset.value.activeIcon) || preset.value.icon,
);

const moreOpen = ref(false);
const statusOpen = ref(false);
// The `collection` action opens a global dialog via emitter rather than a
// local RMenu, so we track its "pinned" lifecycle by hand: flip true on
// click, flip false when the dialog notifies it has closed.
const collectionOpen = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const onCollectionDialogClose = () => {
  collectionOpen.value = false;
};
emitter?.on("closeManageCollectionsDialog", onCollectionDialogClose);
onBeforeUnmount(() =>
  emitter?.off("closeManageCollectionsDialog", onCollectionDialogClose),
);

// Single signal the GameCard `:has()` selectors watch to keep the card's
// hover state painted while an action is in flight — more menu, status
// picker, or collection-manage dialog.
const pinned = computed(() => {
  if (props.action === "more") return moreOpen.value;
  if (props.action === "status") return statusOpen.value;
  if (props.action === "collection") return collectionOpen.value;
  return false;
});

function pickEnum(key: RomUserStatus) {
  // Re-clicking the active enum clears just the enum — gives the user a
  // way to drop the status without also wiping the flags via "Clear all".
  void actions.setStatusEnum(enumStatus.value === key ? null : key);
  statusOpen.value = false;
}

function toggleFlag(key: FlagKey) {
  // Don't close — flags are independent toggles, the user may flip several.
  void actions.setStatus(key);
}

function clearAllStatus() {
  // setStatus(null) wipes both the enum and every flag in one PUT.
  void actions.setStatus(null);
  statusOpen.value = false;
}

// For the play/download links we could render `<router-link>` /
// `<a href>` for right-click-open-in-new-tab support, but keeping
// `<button>` here lets the parent surface own the semantics (the whole
// card is already a link). Both direct actions live in the composable.
function onClick(e: MouseEvent) {
  if (props.action === "more" || props.action === "status") return;
  e.preventDefault();
  e.stopPropagation();
  if (props.action === "collection") collectionOpen.value = true;
  preset.value.onClick?.();
}
</script>

<template>
  <!-- More — opens the shared GameActionsList dropdown. -->
  <RMenu v-if="action === 'more'" v-model="moreOpen" :offset="8" width="260px">
    <template #activator="{ props: activatorProps }">
      <button
        v-bind="activatorProps"
        type="button"
        class="r-v2-game-btn r-v2-game-btn--action-more"
        :class="[
          `r-v2-game-btn--${size}`,
          `r-v2-game-btn--${variant}`,
          {
            'r-v2-game-btn--labelled': withLabel,
            'r-v2-game-btn--pinned': pinned,
          },
        ]"
        :aria-label="preset.label"
        @click.prevent.stop
      >
        <RIcon :icon="displayedIcon" />
        <span v-if="withLabel" class="r-v2-game-btn__label">
          {{ preset.label }}
        </span>
      </button>
    </template>
    <GameActionsList :rom="rom" @close="moreOpen = false" />
  </RMenu>

  <!-- Status — enum picker; icon mirrors the current value, dashed
       border when no status is set. Keeps the per-ROM action set in
       one place instead of a parallel widget. With several states
       active the activator stretches into a multi-icon pill; the
       `orientation` prop chooses row (ribbon) vs column (GameCard). -->
  <RMenu
    v-else-if="action === 'status'"
    v-model="statusOpen"
    :offset="8"
    width="220px"
    :close-on-content-click="false"
  >
    <template #activator="{ props: activatorProps }">
      <button
        v-bind="activatorProps"
        type="button"
        class="r-v2-game-btn"
        :class="[
          `r-v2-game-btn--${size}`,
          `r-v2-game-btn--${variant}`,
          'r-v2-game-btn--action-status',
          `r-v2-game-btn--orient-${orientation}`,
          {
            'r-v2-game-btn--labelled': withLabel,
            'r-v2-game-btn--active': preset.active,
            'r-v2-game-btn--active-status': preset.active,
            'r-v2-game-btn--multi-status': activeStatusIcons.length > 1,
            'r-v2-game-btn--pinned': pinned,
          },
        ]"
        :aria-label="preset.label"
        @click.prevent.stop
      >
        <span v-if="activeStatusIcons.length > 1" class="r-v2-game-btn__icons">
          <RIcon
            v-for="(ic, i) in activeStatusIcons"
            :key="`${ic}-${i}`"
            :icon="ic"
          />
        </span>
        <RIcon v-else :icon="displayedIcon" />
        <span v-if="withLabel" class="r-v2-game-btn__label">
          {{ preset.label }}
        </span>
      </button>
    </template>
    <!-- Enum: single-pick (radio-like). Active row tints brand. -->
    <RMenuItem
      v-for="key in ENUM_KEYS"
      :key="key"
      :icon="STATUS_ICONS[key]"
      :variant="enumStatus === key ? 'active' : 'default'"
      @click="pickEnum(key)"
    >
      {{ romStatusMap[key].text }}
    </RMenuItem>

    <RDivider />

    <!-- Play-status flags: independent toggles (checkbox-like). Active
           rows tint text + icon brand-primary AND show a trailing check,
           so the multi-select reads distinct from the radio-style enum. -->
    <RMenuItem
      v-for="key in PLAY_FLAG_KEYS"
      :key="key"
      :icon="STATUS_ICONS[key]"
      :text-color="isFlagActive(key) ? 'brand-primary' : undefined"
      :icon-color="isFlagActive(key) ? 'brand-primary' : undefined"
      @click="toggleFlag(key)"
    >
      {{ romStatusMap[key].text }}
      <template v-if="isFlagActive(key)" #append>
        <i class="mdi mdi-check r-v2-status-menu__check" aria-hidden="true" />
      </template>
    </RMenuItem>

    <RDivider />

    <!-- Visibility flag — distinct category (controls library
           visibility, not play state) so it lives in its own section. -->
    <RMenuItem
      v-for="key in VISIBILITY_FLAG_KEYS"
      :key="key"
      :icon="STATUS_ICONS[key]"
      :text-color="isFlagActive(key) ? 'brand-primary' : undefined"
      :icon-color="isFlagActive(key) ? 'brand-primary' : undefined"
      @click="toggleFlag(key)"
    >
      {{ romStatusMap[key].text }}
      <template v-if="isFlagActive(key)" #append>
        <i class="mdi mdi-check r-v2-status-menu__check" aria-hidden="true" />
      </template>
    </RMenuItem>

    <template v-if="hasAnyStatus">
      <RDivider />
      <RMenuItem
        icon="mdi-close-circle-outline"
        variant="danger"
        @click="clearAllStatus"
      >
        Clear all
      </RMenuItem>
    </template>
  </RMenu>

  <!-- Plain action — direct click. -->
  <button
    v-else
    type="button"
    class="r-v2-game-btn"
    :class="[
      `r-v2-game-btn--${size}`,
      `r-v2-game-btn--${variant}`,
      `r-v2-game-btn--action-${action}`,
      {
        'r-v2-game-btn--labelled': withLabel,
        'r-v2-game-btn--active': preset.active,
        [`r-v2-game-btn--active-${action}`]: preset.active,
        'r-v2-game-btn--pinned': pinned,
      },
    ]"
    :aria-label="preset.label"
    @click="onClick"
  >
    <RIcon :icon="displayedIcon" />
    <span v-if="withLabel" class="r-v2-game-btn__label">
      {{ preset.label }}
    </span>
  </button>
</template>

<style scoped>
.r-v2-game-btn {
  appearance: none;
  /* Dark glass so the button still reads when sitting on top of a bright
     or busy cover image in the GameCard overlay. In GameDetails the
     backdrop is already a dark blurred cover so this tone lands neutral
     there too. Overlay tokens never theme-flip — they stay dark over
     any cover artwork. */
  border: 1px solid var(--r-color-overlay-border);
  background: var(--r-color-overlay-scrim-soft);
  color: var(--r-color-overlay-fg);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--r-radius-pill);
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  font-weight: var(--r-font-weight-semibold);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-game-btn:hover {
  background: var(--r-color-overlay-scrim-strong);
  border-color: var(--r-color-overlay-border-strong);
  color: var(--r-color-overlay-fg);
}
.r-v2-game-btn:active {
  transform: scale(0.94);
}

/* Size ladder — circular unless `--labelled`. Matches the
   x-small/small/default/large/x-large vocabulary used across primitives. */
.r-v2-game-btn--x-small {
  width: 22px;
  height: 22px;
  font-size: 10px;
}
.r-v2-game-btn--x-small :deep(.mdi) {
  font-size: 14px;
}
.r-v2-game-btn--small {
  width: 28px;
  height: 28px;
  font-size: 11px;
}
.r-v2-game-btn--small :deep(.mdi) {
  font-size: 16px;
}
.r-v2-game-btn--default {
  width: 40px;
  height: 40px;
  font-size: 13px;
}
.r-v2-game-btn--default :deep(.mdi) {
  font-size: 20px;
}
.r-v2-game-btn--large {
  width: 44px;
  height: 44px;
  font-size: 14px;
}
.r-v2-game-btn--large :deep(.mdi) {
  font-size: 22px;
}
.r-v2-game-btn--x-large {
  width: 52px;
  height: 52px;
  font-size: 15px;
}
.r-v2-game-btn--x-large :deep(.mdi) {
  font-size: 26px;
}

/* Labelled — expands to a pill with text. Used by Play in the
   GameDetails header. Height stays the same as the circular variant so
   it can live in the same row without visual jumps. */
.r-v2-game-btn--labelled {
  width: auto;
  padding: 0 18px;
}
.r-v2-game-btn--labelled.r-v2-game-btn--x-small {
  padding: 0 8px;
}
.r-v2-game-btn--labelled.r-v2-game-btn--small {
  padding: 0 12px;
}
.r-v2-game-btn--labelled.r-v2-game-btn--large {
  padding: 0 24px;
}
.r-v2-game-btn--labelled.r-v2-game-btn--x-large {
  padding: 0 32px;
}

/* Surface — RTag-style translucent grey. Used in the GameDetails
   header where buttons sit on the page background (not over cover
   art) — matches the visual vocabulary of RTag and RSelect there. */
.r-v2-game-btn--surface {
  background: var(--r-color-surface);
  border-color: var(--r-color-border-strong);
  color: var(--r-color-fg-secondary);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
.r-v2-game-btn--surface:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
  color: var(--r-color-fg);
}

/* Emphasized — the primary-action look (white on dark). Used by Play. */
.r-v2-game-btn--emphasized {
  background: var(--r-color-overlay-emphasis-bg) !important;
  border-color: var(--r-color-overlay-emphasis-bg) !important;
  color: var(--r-color-overlay-emphasis-fg) !important;
}
.r-v2-game-btn--emphasized:hover {
  background: var(--r-color-overlay-emphasis-bg-hover) !important;
  transform: translateY(-1px);
}
.r-v2-game-btn--emphasized:active {
  transform: scale(0.96);
}

/* Active-state colour swaps per action. */
.r-v2-game-btn--active-favorite {
  color: var(--r-color-brand-primary) !important;
}

/* Status — dashed border when no status is set, signals "click to
   pick". Once set, the button uses the regular solid border + the
   status icon shows the choice. */
.r-v2-game-btn--action-status:not(.r-v2-game-btn--active-status) {
  border-style: dashed;
}

/* Multi-status — the button stretches to fit every active state's
   icon. Width/height go auto with a min that keeps the single-state
   diameter, so 0/1 active still reads as a circle. The icon row/column
   lives in `__icons`. */
.r-v2-game-btn__icons {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.r-v2-game-btn--orient-horizontal .r-v2-game-btn__icons {
  flex-direction: row;
  gap: 6px;
}
.r-v2-game-btn--orient-vertical .r-v2-game-btn__icons {
  flex-direction: column;
  gap: 4px;
}

.r-v2-game-btn--multi-status {
  width: auto;
  height: auto;
  border-radius: var(--r-radius-pill);
}
.r-v2-game-btn--multi-status.r-v2-game-btn--x-small {
  min-width: 22px;
  min-height: 22px;
  padding: 3px 6px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--small {
  min-width: 28px;
  min-height: 28px;
  padding: 4px 8px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--default {
  min-width: 40px;
  min-height: 40px;
  padding: 4px 10px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--large {
  min-width: 44px;
  min-height: 44px;
  padding: 4px 12px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--x-large {
  min-width: 52px;
  min-height: 52px;
  padding: 4px 14px;
}
/* Vertical: swap the padding axis so the pill grows tall, not wide. */
.r-v2-game-btn--multi-status.r-v2-game-btn--orient-vertical.r-v2-game-btn--x-small {
  padding: 6px 3px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--orient-vertical.r-v2-game-btn--small {
  padding: 8px 4px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--orient-vertical.r-v2-game-btn--default {
  padding: 10px 4px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--orient-vertical.r-v2-game-btn--large {
  padding: 12px 4px;
}
.r-v2-game-btn--multi-status.r-v2-game-btn--orient-vertical.r-v2-game-btn--x-large {
  padding: 14px 4px;
}

/* Trailing check on the flag rows of the status menu — signals the
   boolean is on. Brand color so it pops against the neutral row. */
.r-v2-status-menu__check {
  font-size: 12px;
  color: var(--r-color-brand-primary);
}
</style>
