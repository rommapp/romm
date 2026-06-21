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
import { computed, inject } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { RomUserData, RomUserStatus } from "@/__generated__";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { PlayingStatus } from "@/utils";
import { getDownloadLink, getDownloadPath, isNintendoDSRom } from "@/utils";
import { useCan } from "@/v2/composables/useCan";
import { useCanPlay } from "@/v2/composables/useCanPlay";
import { useSnackbar } from "@/v2/composables/useSnackbar";

export function useGameActions(getRom: () => SimpleRom | null | undefined) {
  const { t } = useI18n();
  const router = useRouter();
  const emitter = inject<Emitter<Events>>("emitter");
  const snackbar = useSnackbar();
  const romsStore = storeRoms();
  const canCreateCollection = useCan("collection.create");
  const canEditCollection = useCan("collection.edit");
  const { isFavorite, toggleFavorite } = useFavoriteToggle(emitter);
  const { canPlay, canPlayEJS, canPlayRuffle } = useCanPlay(getRom);

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
    if (canPlayEJS.value) {
      router.push(`/rom/${rom.id}/ejs`);
    } else if (canPlayRuffle.value) {
      router.push(`/rom/${rom.id}/ruffle`);
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
    try {
      if (typeof nav.share === "function") {
        await nav.share(shareData);
        return;
      }
      await navigator.clipboard.writeText(url);
      snackbar.success(t("rom.snackbar-link-copied"), {
        icon: "mdi-link-variant",
      });
    } catch {
      // user cancelled or clipboard denied — nothing to do
    }
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
  // it currently sits in the Continue Playing row. Per-user data, so any
  // authenticated role may clear their own; backend is the real gate.
  const canRemoveFromContinuePlaying = computed(() =>
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
