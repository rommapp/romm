import type { Emitter } from "mitt";
import { computed, inject, type InjectionKey, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { RomUserData, RomUserStatus } from "@/__generated__";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";
import { useUISettings } from "@/composables/useUISettings";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import type { DetailedRom, SimpleRom } from "@/stores/roms";
import { useStreamingStore } from "@/stores/streaming";
import type { Events } from "@/types/emitter";
import type { PlayingStatus } from "@/utils";
import {
  getDownloadLink,
  getDownloadPath,
  getSoleRomFile,
  isNintendoDSRom,
} from "@/utils";
import { useCan } from "@/v2/composables/useCan";
import { useCanPlay } from "@/v2/composables/useCanPlay";
import { useClipboard } from "@/v2/composables/useClipboard";
import { useConfirm } from "@/v2/composables/useConfirm";
import { confirmJoinStream } from "@/v2/composables/useJoinStreamConfirm";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useScanTrigger } from "@/v2/composables/useScanTrigger";
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

type PlayerSlug = "stream" | "jsdos" | "ejs" | "pico8" | "easyrpg" | "ruffle";

// A conversion can take a while on large discs; stop polling after about an hour.
const FORMAT_POLL_SECONDS = 30;
const FORMAT_POLL_LIMIT = 120;
// Shared across menus so a second click doesn't start another poll and download.
const pendingFormatDownloads = new Set<string>();

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
  const heartbeat = storeHeartbeat();
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
  const { startScan } = useScanTrigger();
  const {
    canPlay,
    canPlayEJS,
    canPlayJsDos,
    canPlayPico8,
    canPlayEasyRpg,
    canPlayRuffle,
    canPlayStream,
    canPlayNative,
  } = useCanPlay(getRom);
  const streamingStore = useStreamingStore();

  // Streaming is offered as its own action rather than as the winner of a
  // precedence rule, so each player needs a gate of its own.
  const canPlayInBrowser = computed(
    () =>
      canPlayEJS.value ||
      canPlayJsDos.value ||
      canPlayPico8.value ||
      canPlayEasyRpg.value ||
      canPlayRuffle.value,
  );

  // Whether the Play button has a play page to open. The desktop shell's own
  // emulator is offered from that page alongside the in-browser core, so a
  // platform only the shell can run still needs the button.
  const canPlayLocally = computed(
    () => canPlayInBrowser.value || canPlayNative.value,
  );

  // Download, the copied link and the QR code all resolve to the download
  // endpoint, which has nothing to serve without a file behind the rom.
  const canDownload = computed(() => Boolean(getRom()?.has_file_on_disk));

  // Only the detailed rom carries them, already narrowed to what this caller
  // can convert its single file to.
  const downloadFormats = computed<string[]>(() => {
    const rom = getRom() as Partial<DetailedRom> | null | undefined;
    if (!rom || !canDownload.value) return [];
    return rom.download_formats ?? [];
  });

  // Names the box the session runs on, so a library served by more than one
  // container says which the button reaches.
  const streamLabel = computed(
    () =>
      streamingStore.containerLabelForPlatform(getRom()?.platform_slug) ?? "",
  );

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

  // The wording every surface offering these actions uses. Held here so the
  // action button and the overflow menu cannot name the same action
  // differently.
  const streamActionLabel = computed(() =>
    streamLabel.value
      ? t("rom.stream-on", { container: streamLabel.value })
      : t("rom.stream"),
  );

  const joinActionLabel = computed(() =>
    joinHostLabel.value
      ? t("rom.join-session-of", { user: joinHostLabel.value })
      : t("rom.join-session"),
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

  /** Set the status enum, leaving the boolean status flags alone. */
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

  /** Set a per-user score; null is sent as 0, the backend's "no value". */
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

  /** Gated on permission, not on existing collections, so a ROM can start the first one. */
  const canManageCollections = computed(
    () => canCreateCollection.value || canEditCollection.value,
  );

  const canShareQR = computed(() => {
    const rom = getRom();
    return Boolean(rom && rom.has_file_on_disk && isNintendoDSRom(rom));
  });

  const canInstallOnDevice = computed(() => {
    const rom = getRom();
    const deviceInstall = heartbeat.value.DEVICE_INSTALL;
    return Boolean(
      rom?.has_file_on_disk &&
      deviceInstall.ENABLED &&
      !deviceInstall.EXCLUDED_PLATFORM_SLUGS.includes(
        rom.platform_slug.toLowerCase(),
      ) &&
      auth.scopes.includes("devices.read") &&
      auth.scopes.includes("devices.write") &&
      auth.scopes.includes("roms.read"),
    );
  });

  function installOnDevice() {
    const rom = getRom();
    if (!rom) return;
    emitter?.emit("showInstallOnDeviceDialog", rom);
  }

  const canOpenInFlashpoint = computed(() => {
    const rom = getRom();
    return Boolean(
      rom?.flashpoint_id && FLASHPOINT_ID_RE.test(rom.flashpoint_id),
    );
  });

  // Launching a game the user deliberately shelved asks first. `retired` /
  // `never_playing` encode an opt-in "don't play" intent; the prompt is
  // gated by a per-user preference (on by default).
  const needsLaunchConfirm = computed(() => {
    const status = getRom()?.rom_user?.status;
    return (
      confirmProtectedLaunch.value &&
      (status === "retired" || status === "never_playing")
    );
  });

  async function play(player: PlayTarget = "auto") {
    const rom = getRom();
    if (!rom) return;

    const status = rom.rom_user?.status;
    if (needsLaunchConfirm.value) {
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

    const target = playPath(player);
    if (!target) return;

    // The launch "load" flourish (disc/cartridge insert) lives on the
    // player view itself (see EmulatorJS's onPlay), so navigation is
    // immediate here. When the caller supplies a cover element (the gallery
    // card / detail hero), morph it into the player's hero cover: the same
    // `rom-cover-<id>` tag the player paints statically. Degrades to a plain
    // push where view transitions aren't available.
    const el = options.coverEl?.();
    if (el) {
      // Await the push inside the transition so the browser snapshots the
      // player view *after* it has rendered its hero cover (which carries the
      // same `rom-cover-<id>` tag); otherwise there's no element to morph to.
      morphTransition({ el, name: `rom-cover-${rom.id}` }, async () => {
        await router.push(target);
      });
    } else {
      router.push(target);
    }
  }

  // A platform can be served by both an in-browser core and a streaming
  // container, and they are different products (local latency versus the
  // container's own emulator and save library). The caller says which it
  // wants; "auto" keeps the single-button surfaces working by preferring
  // the stream, as they did before either could be asked for by name.
  /** Path `play(player)` opens; surfaces rendering the launch as a link point at it too. */
  function playPath(player: PlayTarget = "auto"): string | null {
    const rom = getRom();
    if (!rom) return null;
    let slug: PlayerSlug | null = null;
    if (player === "stream") slug = canPlayStream.value ? "stream" : null;
    else if (player === "auto" && canPlayStream.value) slug = "stream";
    else if (canPlayJsDos.value) slug = "jsdos";
    else if (canPlayEJS.value) slug = "ejs";
    else if (canPlayPico8.value) slug = "pico8";
    else if (canPlayEasyRpg.value) slug = "easyrpg";
    else if (canPlayRuffle.value) slug = "ruffle";
    // Last, because the play page offers the native launch beside whichever
    // in-browser core the branches above would have picked.
    else if (canPlayNative.value) slug = "ejs";
    return slug ? `/rom/${rom.id}/${slug}` : null;
  }

  // Joining is its own navigation: the stream view claims a container when it
  // opens normally, so the join intent has to reach it in the URL. Confirming
  // first is what stands in for the start page, which a joiner never sees:
  // they land in someone else's running game with no settings of their own.
  async function joinStream() {
    const rom = getRom();
    if (!rom || !canJoinStream.value) return;
    await confirmJoinStream(
      { t, router, confirm },
      {
        romId: rom.id,
        romName: rom.name ?? rom.fs_name_no_ext ?? "",
        hostUsername: joinHostLabel.value || null,
        container: joinableSession.value?.container ?? null,
      },
    );
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

  async function downloadAs(format: string) {
    const rom = getRom();
    const file = rom ? getSoleRomFile(rom) : null;
    if (!rom || !file) return;
    const label = format.toUpperCase();
    const href = getDownloadPath({ rom, fileIDs: [file.id], format });
    if (pendingFormatDownloads.has(href)) return;
    pendingFormatDownloads.add(href);
    try {
      let probe = await romApi.probeFormatDownload(href);
      if (probe.status === 202) {
        snackbar.info(t("rom.download-as-preparing", { format: label }));
      }
      let polls = 0;
      while (probe.status === 202 && polls++ < FORMAT_POLL_LIMIT) {
        const seconds = probe.retryAfterSeconds ?? FORMAT_POLL_SECONDS;
        await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
        probe = await romApi.probeFormatDownload(href);
      }
      if (probe.status === 200 || probe.status === 206) {
        await romApi.downloadRom({ rom, fileIDs: [file.id], format });
        return;
      }
    } catch {
      // A failed probe is reported like a format that can't be served.
    } finally {
      pendingFormatDownloads.delete(href);
    }
    snackbar.error(t("rom.download-as-unavailable", { format: label }), {
      persist: { body: rom.name ?? rom.fs_name, link: `/rom/${rom.id}` },
    });
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
        // Dismissing the native share sheet rejects the promise.
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
    await clipboard.copy(link, {
      successMessage: t("rom.snackbar-download-link-copied"),
      successIcon: "mdi-link-variant",
      fallback: () => emitter?.emit("showCopyDownloadLinkDialog", link),
    });
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

  // Reconciling one rom's files contacts no provider, so it needs no dialog: it goes
  // straight to the socket with an empty source list.
  function refreshFiles() {
    const rom = getRom();
    if (!rom) return;
    const started = startScan([
      {
        platforms: [rom.platform_id],
        roms_ids: [rom.id],
        type: "quick",
        apis: [],
      },
    ]);
    if (!started) return;
    snackbar.info(
      t("rom.refreshing-files", { name: rom.name ?? rom.fs_name }),
      {
        icon: "mdi-loading mdi-spin",
      },
    );
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

  /** Requires roms.user.write, the scope the backend checks. */
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
    canInstallOnDevice,
    canOpenInFlashpoint,
    canDownload,
    downloadFormats,
    canPlay,
    canPlayStream,
    canPlayLocally,
    streamLabel,
    streamActionLabel,
    canJoinStream,
    joinHostLabel,
    joinActionLabel,
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
    needsLaunchConfirm,
    play,
    playPath,
    goToPlatform,
    platformPath,
    download,
    downloadAs,
    favorite,
    share,
    shareQR,
    installOnDevice,
    openInFlashpoint,
    copyDownloadLink,
    manageCollections,
    refreshMetadata,
    refreshFiles,
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
