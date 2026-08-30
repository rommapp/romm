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
import { computed, inject, type InjectionKey, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { RomUserData, RomUserStatus } from "@/__generated__";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";
import { useUISettings } from "@/composables/useUISettings";
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
import { useConfirm } from "@/v2/composables/useConfirm";
import { useJoinStreamConfirm } from "@/v2/composables/useJoinStreamConfirm";
import { useRomSync } from "@/v2/composables/useRomSync";
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

/** Which player a launch is asking for. "auto" lets availability decide. */
export type PlayTarget = "auto" | "local" | "stream";

// Validate flashpoint game IDs are UUIDs
const FLASHPOINT_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function useGameActions(
  getRom: () => SimpleRom | null | undefined,
  options: GameActionsOptions = {},
) {
  const { t } = useI18n();
  const router = useRouter();
  const { morphTransition } = useViewTransition();
  const emitter = inject<Emitter<Events>>("emitter");
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const { confirmProtectedLaunch } = useUISettings();
  const clipboard = useClipboard();
  const romsStore = storeRoms();
  const { syncCachedRom, refreshAfterUserStateChange, refreshIfOrderedBy } =
    useRomSync();
  const auth = storeAuth();
  const canCreateCollection = useCan("collection.create");
  const canEditCollection = useCan("collection.edit");
  // Write/destructive gates, mirroring the backend grants. Surfaces that
  // offer these actions hide them outright rather than letting the request
  // 403 and surface a permission error the user can't act on.
  const canEdit = useCan("rom.edit");
  const canMatch = useCan("rom.match");
  const canRefresh = useCan("rom.refresh");
  const hasDeleteGrant = useCan("rom.delete");
  // `POST /roms/delete` gates on ROMS_WRITE, and a bare DELETE grant projects
  // to no scope at all, so the delete grant alone can't authorise the call.
  // Require the write grant too (`rom.edit` is its proxy) or the menu offers a
  // delete that 403s.
  const canDelete = computed(() => hasDeleteGrant.value && canEdit.value);
  const { isFavorite, toggleFavorite } = useFavoriteToggle(emitter);
  const { canPlay, canPlayEJS, canPlayJsDos, canPlayRuffle, canPlayStream } =
    useCanPlay(getRom);
  const streamingStore = useStreamingStore();

  // Streaming is offered as its own action rather than as the winner of a
  // precedence rule, so each player needs a gate of its own.
  const canPlayInBrowser = computed(
    () => canPlayEJS.value || canPlayJsDos.value || canPlayRuffle.value,
  );

  // Download, the copied link and the QR code all resolve to the download
  // endpoint, which has nothing to serve without a file behind the rom.
  const canDownload = computed(() => Boolean(getRom()?.has_file_on_disk));

  // Names the box the session runs on, so a library served by more than one
  // container says which the button reaches.
  const streamLabel = computed(() => {
    const rom = getRom();
    if (!rom) return "";
    return streamingStore.containerForPlatform(rom.platform_slug)?.label ?? "";
  });

  // Asked for here so every surface offering Join has the list, not just the
  // game details page. The store collapses concurrent callers into one request
  // and holds the answer for a freshness window, so a gallery of cards costs
  // what a single card costs.
  watch(
    canPlayStream,
    (can) => {
      if (can) void streamingStore.fetchJoinableSessions();
    },
    { immediate: true },
  );

  // A session someone else opened to other players on this exact ROM. Read
  // from the store, never fetched here: this composable is instantiated once
  // per GameActionBtn, and a fetch per instance would be a request storm.
  const joinableSession = computed(() => {
    const rom = getRom();
    if (!rom) return null;
    return streamingStore.joinableForRom(rom.id);
  });

  const canJoinStream = computed(
    () => canPlayStream.value && joinableSession.value !== null,
  );

  const joinHostLabel = computed(
    () => joinableSession.value?.host_username ?? "",
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
    syncCachedRom(rom);
    try {
      await romApi.updateUserRomProps({ romId: rom.id, data });
    } catch {
      Object.assign(rom.rom_user, before);
      syncCachedRom(rom);
      snackbar.error(t("rom.snackbar-update-status-failed"), {
        icon: "mdi-alert-circle-outline",
      });
    }
    refreshAfterUserStateChange();
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
    syncCachedRom(rom);

    try {
      await romApi.updateUserRomProps({ romId: rom.id, data });
    } catch {
      Object.assign(rom.rom_user, before);
      syncCachedRom(rom);
      snackbar.error(t("rom.snackbar-update-status-failed"), {
        icon: "mdi-alert-circle-outline",
      });
    }
    refreshAfterUserStateChange();
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
    syncCachedRom(rom);

    try {
      await romApi.updateUserRomProps({ romId: rom.id, data });
    } catch {
      Object.assign(rom.rom_user, before);
      syncCachedRom(rom);
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
    return Boolean(rom && rom.has_file_on_disk && isNintendoDSRom(rom));
  });

  const canOpenInFlashpoint = computed(() => {
    const rom = getRom();
    return Boolean(
      rom?.flashpoint_id && FLASHPOINT_ID_RE.test(rom.flashpoint_id),
    );
  });

  async function play(player: PlayTarget = "auto") {
    const rom = getRom();
    if (!rom) return;

    // Guard launching a game the user deliberately shelved. `retired` /
    // `never_playing` encode an opt-in "don't play" intent, so confirm
    // before booting one. Gated by a per-user preference (on by default).
    const status = rom.rom_user?.status;
    if (
      confirmProtectedLaunch.value &&
      (status === "retired" || status === "never_playing")
    ) {
      const ok = await confirm({
        title: t("rom.confirm-launch-protected-title"),
        body: t("rom.confirm-launch-protected-body", {
          name: rom.name ?? rom.fs_name_no_ext ?? "",
          status: t(
            status === "retired"
              ? "rom.status-retired"
              : "rom.status-never-playing",
          ),
        }),
        confirmText: t("play.play"),
        tone: "warning",
      });
      if (!ok) return;
    }

    // A platform can be served by both an in-browser core and a streaming
    // container, and they are different products (local latency versus the
    // container's own emulator and save library). The caller says which it
    // wants; "auto" keeps the single-button surfaces working by preferring
    // the stream, as they did before either could be asked for by name.
    const streaming =
      player === "stream" || (player === "auto" && canPlayStream.value);
    const inBrowser = player === "local" || player === "auto";

    // EmulatorJS and js-dos need SharedArrayBuffer. Nginx only attaches the
    // necessary COOP/COEP headers to the player document, so an SPA navigation
    // cannot enable cross-origin isolation. Load the document directly instead.
    const isolated = canPlayJsDos.value
      ? "jsdos"
      : canPlayEJS.value
        ? "ejs"
        : null;
    if (!streaming && inBrowser && isolated) {
      window.location.assign(`/rom/${rom.id}/${isolated}`);
      return;
    }

    // The launch "load" flourish (disc/cartridge insert) lives on the
    // player view itself — see EmulatorJS's onPlay — so navigation is
    // immediate here.
    let path: string | null = null;
    if (streaming && canPlayStream.value) path = `/rom/${rom.id}/stream`;
    else if (inBrowser && canPlayRuffle.value) path = `/rom/${rom.id}/ruffle`;
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

  // Joining is its own navigation: the stream view claims a container when it
  // opens normally, so the join intent has to reach it in the URL. Confirming
  // first is what stands in for the start page, which a joiner never sees:
  // they land in someone else's running game with no settings of their own.
  const { joinStream: confirmAndJoinStream } = useJoinStreamConfirm();
  async function joinStream() {
    const rom = getRom();
    if (!rom || !canJoinStream.value) return;
    await confirmAndJoinStream({
      romId: rom.id,
      romName: rom.name ?? rom.fs_name_no_ext ?? "",
      hostUsername: joinHostLabel.value || null,
    });
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
    refreshAfterUserStateChange();
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

  // Launch the game in installed Flashpoint
  function openInFlashpoint() {
    const rom = getRom();
    if (!rom?.flashpoint_id || !FLASHPOINT_ID_RE.test(rom.flashpoint_id))
      return;
    const a = document.createElement("a");
    a.href = `flashpoint://${rom.flashpoint_id}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
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
      syncCachedRom(rom);
      // Clearing the timestamp moves the card in a last-played-ordered
      // gallery, and the in-place mutation above leaves nothing for
      // `applyRomWrite` to diff against.
      refreshIfOrderedBy("last_played");
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
    canOpenInFlashpoint,
    canDownload,
    canPlay,
    canPlayStream,
    canPlayInBrowser,
    streamLabel,
    canJoinStream,
    joinHostLabel,
    joinStream,
    canRemoveFromContinuePlaying,
    canEdit,
    canDelete,
    canMatch,
    canRefresh,
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
    openInFlashpoint,
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
