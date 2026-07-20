// useGameActions — shared action handlers for a ROM. One place for
// play / download / favorite / share / match / refresh / edit / delete /
// add-to-collection. Consumed by every surface that shows per-ROM actions
// (MoreMenu on GameCard, MoreMenu in GameDetails header, etc.) so the
// action list stays in sync.
//
// Usage:
//   const actions = useGameActions(() => rom.value);
//   actions.play(); actions.toggleFavorite(); …
//   actions.isFavorite     // reactive Ref<boolean>
//   actions.canManageCollections  // reactive Ref<boolean>
import type { Emitter } from "mitt";
import { computed, inject, type InjectionKey } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { RomUserData, RomUserStatus } from "@/__generated__";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import type { SimpleRom } from "@/stores/roms";
import { useStreamingStore } from "@/stores/streaming";
import type { Events } from "@/types/emitter";
import type { PlayingStatus } from "@/utils";
import { getDownloadLink, getDownloadPath, isNintendoDSRom } from "@/utils";
import { useCan } from "@/v2/composables/useCan";
import { useCanPlay } from "@/v2/composables/useCanPlay";
import { useClipboard } from "@/v2/composables/useClipboard";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useViewTransition } from "@/v2/composables/useViewTransition";

export interface GameActionsOptions {
  /** Resolver for the cover element to morph from when `play()` navigates to
   *  the player view. When it returns an element, the navigation runs through
   *  a shared-element view transition (cover → player hero, same `rom-cover-`
   *  tag the destination paints); otherwise navigation is immediate. The
   *  GameCard passes its GameCover box so clicking Play in the gallery morphs
   *  the cover into /ejs the same way clicking the card morphs into details. */
  coverEl?: () => HTMLElement | null;
}

export function useGameActions(
  getRom: () => SimpleRom | null | undefined,
  options: GameActionsOptions = {},
) {
  const { t } = useI18n();
  const router = useRouter();
  const { morphTransition } = useViewTransition();
  const emitter = inject<Emitter<Events>>("emitter");
  const snackbar = useSnackbar();
  const clipboard = useClipboard();
  const romsStore = storeRoms();
  const auth = storeAuth();
  const canCreateCollection = useCan("collection.create");
  const canEditCollection = useCan("collection.edit");
  const { isFavorite, toggleFavorite } = useFavoriteToggle(emitter);
  const { canPlayEJS, canPlayRuffle } = useCanPlay(getRom);
  const streamingStore = useStreamingStore();

  // Streaming is the preferred way to play where a container is
  // configured for the platform — the native emulator runs in a
  // separate container and RomM streams it back. Wins over in-browser
  // EJS/Ruffle when both are available.
  const canPlayStream = computed(() =>
    Boolean(streamingStore.containerForPlatform(getRom()?.platform_slug)),
  );
  const canPlay = computed(
    () => canPlayStream.value || canPlayEJS.value || canPlayRuffle.value,
  );

  const isFavorited = computed(() => {
    const rom = getRom();
    return rom ? Boolean(isFavorite(rom)) : false;
  });

  // Mirrors the priority used in GameDetails.vue's statusDisplay so the
  // GameCard badge and the detail header always agree on which slot is
  // "current".
  const currentStatusKey = computed<PlayingStatus | null>(() => {
    const ru = getRom()?.rom_user;
    if (!ru) return null;
    if (ru.now_playing) return "now_playing";
    if (ru.backlogged) return "backlogged";
    if (ru.hidden) return "hidden";
    return ru.status ?? null;
  });

  // Writes only the enum `status` field (incomplete | finished | …).
  // Distinct from setStatus(null) which v1 used to nuke every status
  // signal at once — Overview's enum dropdown wants to clear only its
  // own field without touching the boolean flags.
  async function setStatusEnum(value: RomUserStatus | null) {
    const rom = getRom();
    if (!rom?.rom_user) return;
    const data: Partial<RomUserData> = { status: value };
    const before = { ...rom.rom_user };
    rom.rom_user.status = value;
    romsStore.update(rom);
    try {
      await romApi.updateUserRomProps({ romId: rom.id, data });
    } catch {
      Object.assign(rom.rom_user, before);
      romsStore.update(rom);
      snackbar.error(t("rom.snackbar-update-status-failed"), {
        icon: "mdi-alert-circle-outline",
      });
    }
  }

  // Toggle semantics match v1's Personal tab: booleans flip independently,
  // the enum status flips/clears on re-pick. `null` clears everything.
  async function setStatus(next: PlayingStatus | null) {
    const rom = getRom();
    if (!rom?.rom_user) return;

    let data: Partial<RomUserData>;
    if (next === null) {
      data = {
        now_playing: false,
        backlogged: false,
        hidden: false,
        status: null,
      };
    } else if (
      next === "now_playing" ||
      next === "backlogged" ||
      next === "hidden"
    ) {
      data = { [next]: !rom.rom_user[next] };
    } else {
      data = { status: rom.rom_user.status === next ? null : next };
    }

    const before = { ...rom.rom_user };
    Object.assign(rom.rom_user, data);
    romsStore.update(rom);

    try {
      await romApi.updateUserRomProps({ romId: rom.id, data });
    } catch {
      Object.assign(rom.rom_user, before);
      romsStore.update(rom);
      snackbar.error(t("rom.snackbar-update-status-failed"), {
        icon: "mdi-alert-circle-outline",
      });
    }
  }

  // Optimistic write of a numeric per-user field (rating | difficulty
  // | completion). Mirrors setStatus' revert-on-error pattern. v1 stores
  // 0 to mean "no value" — we accept null at the call site and coerce
  // to 0 so the backend keeps a uniform shape.
  async function setScore(
    field: "rating" | "difficulty" | "completion",
    value: number | null,
  ) {
    const rom = getRom();
    if (!rom?.rom_user) return;

    const next = value ?? 0;
    const data: Partial<RomUserData> = { [field]: next };
    const before = { ...rom.rom_user };
    rom.rom_user[field] = next;
    romsStore.update(rom);

    try {
      await romApi.updateUserRomProps({ romId: rom.id, data });
    } catch {
      Object.assign(rom.rom_user, before);
      romsStore.update(rom);
      snackbar.error(t("rom.snackbar-update-field-failed", { field }), {
        icon: "mdi-alert-circle-outline",
      });
    }
  }

  // Permission-driven, not state-driven. The previous "count > 0"
  // check hid the entry exactly when the user needed it most — to
  // create the first collection from a ROM (ManageCollectionsDialog
  // bundles toggle + create flows in one surface). Backend rejects
  // unauthorised writes regardless, so this gate is purely UX.
  const canManageCollections = computed(
    () => canCreateCollection.value || canEditCollection.value,
  );

  const canShareQR = computed(() => {
    const rom = getRom();
    return rom ? isNintendoDSRom(rom) : false;
  });

  function play() {
    const rom = getRom();
    if (!rom) return;
    // The launch "load" flourish (disc/cartridge insert) lives on the
    // player view itself — see EmulatorJS's onPlay — so navigation is
    // immediate here.
    let path: string | null = null;
    if (canPlayStream.value) path = `/rom/${rom.id}/stream`;
    else if (canPlayEJS.value) path = `/rom/${rom.id}/ejs`;
    else if (canPlayRuffle.value) path = `/rom/${rom.id}/ruffle`;
    if (!path) return;
    const target = path;
    // When the caller supplies a cover element (the gallery card / detail
    // hero), morph it into the player's hero cover — same `rom-cover-<id>`
    // tag the player paints statically. Degrades to a plain push where view
    // transitions aren't available.
    const el = options.coverEl?.();
    if (el) {
      // Await the push inside the transition so the browser snapshots the
      // player view *after* it has rendered its hero cover (which carries the
      // same `rom-cover-<id>` tag) — otherwise there's no element to morph to.
      morphTransition({ el, name: `rom-cover-${rom.id}` }, async () => {
        await router.push(target);
      });
    } else {
      router.push(target);
    }
  }

  const platformPath = computed(() => {
    const rom = getRom();
    return rom ? `/platform/${rom.platform_id}` : null;
  });

  function goToPlatform() {
    const path = platformPath.value;
    if (path) router.push(path);
  }

  function download() {
    const rom = getRom();
    if (!rom) return;
    const href = getDownloadPath({ rom });
    const a = document.createElement("a");
    a.href = href;
    a.download = rom.fs_name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function favorite() {
    const rom = getRom();
    if (!rom) return;
    await toggleFavorite(rom);
  }

  async function share() {
    const rom = getRom();
    if (!rom) return;
    const url = window.location.origin + `/rom/${rom.id}`;
    const title = rom.name ?? rom.fs_name_no_ext ?? "ROM";
    const shareData = { title, text: title, url };
    const nav = navigator as Navigator & {
      share?: (data: typeof shareData) => Promise<void>;
    };
    if (typeof nav.share === "function") {
      try {
        await nav.share(shareData);
      } catch {
        // user cancelled the native share sheet — nothing to do
      }
      return;
    }
    await clipboard.copy(url, {
      successMessage: t("rom.snackbar-link-copied"),
      successIcon: "mdi-link-variant",
    });
  }

  function shareQR() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showQRCodeDialog", rom);
  }

  // Copies the API download URL (origin + /api/roms/.../content/...) so
  // the user can paste it into another device or share it. v1 used this
  // for handhelds that can ingest a direct download URL. Falls back to a
  // dialog displaying the link when the Clipboard API isn't available
  // (insecure context, older browsers).
  async function copyDownloadLink() {
    const rom = getRom();
    if (!rom) return;
    const link = getDownloadLink({ rom });
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(link);
        snackbar.success(t("rom.snackbar-download-link-copied"), {
          icon: "mdi-link-variant",
        });
        return;
      } catch {
        // fall through to dialog fallback
      }
    }
    emitter?.emit("showCopyDownloadLinkDialog", link);
  }

  function manageCollections() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showManageCollectionsDialog", [rom]);
  }

  function refreshMetadata() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showRefreshMetadataDialog", rom);
  }

  function edit() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showEditRomDialog", rom);
  }

  function match() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showMatchRomDialog", rom);
  }

  function remove() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showDeleteRomDialog", [rom]);
  }

  // Only relevant while the ROM carries a `last_played` timestamp — i.e.
  // it currently sits in the Continue Playing row. Also requires the
  // `roms.user.write` scope to match the backend gate and avoid a 403.
  const canRemoveFromContinuePlaying = computed(
    () =>
      auth.scopes.includes("roms.user.write") &&
      Boolean(getRom()?.rom_user?.last_played),
  );

  // Clears the per-user `last_played` so the ROM drops out of Continue
  // Playing. Mirrors v1's AdminMenu.resetLastPlayed: update the backend,
  // wipe the local timestamp, and prune the cached continue-playing list.
  async function removeFromContinuePlaying() {
    const rom = getRom();
    if (!rom) return;
    try {
      await romApi.updateUserRomProps({
        romId: rom.id,
        data: {},
        removeLastPlayed: true,
      });
      if (rom.rom_user) rom.rom_user.last_played = null;
      romsStore.update(rom);
      romsStore.removeFromContinuePlaying(rom);
      snackbar.success(t("rom.snackbar-removed-from-playing"), {
        icon: "mdi-check-bold",
      });
    } catch {
      snackbar.error(t("rom.snackbar-remove-from-playing-failed"), {
        icon: "mdi-alert-circle-outline",
      });
    }
  }

  return {
    isFavorited,
    canManageCollections,
    canShareQR,
    canPlay,
    canPlayStream,
    canRemoveFromContinuePlaying,
    currentStatusKey,
    setStatus,
    setStatusEnum,
    setScore,
    play,
    goToPlatform,
    platformPath,
    download,
    favorite,
    share,
    shareQR,
    copyDownloadLink,
    manageCollections,
    refreshMetadata,
    edit,
    match,
    remove,
    removeFromContinuePlaying,
  };
}

export type GameActions = ReturnType<typeof useGameActions>;

/** Injection key for sharing one `useGameActions` instance down a subtree.
 *  A GameCard hosts ~6 GameActionBtn children (play / download / collection /
 *  favorite / status / more); each one re-instantiating the full composable
 *  (i18n + router + emitter + two stores + `useCan`×2 + favorite/can-play
 *  computeds) is what made a virtualised grid of cards thousands of live
 *  instances. The card creates a single instance and `provide`s it; each
 *  button `inject`s and reuses it, falling back to its own only when used
 *  standalone (GameDetails header, list rows) with no provider. */
export const GAME_ACTIONS_KEY: InjectionKey<GameActions> =
  Symbol("v2:gameActions");
