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
import { useRouter } from "vue-router";
import type { RomUserData, RomUserStatus } from "@/__generated__";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storeRoms from "@/stores/roms";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { PlayingStatus } from "@/utils";
import { getDownloadPath, isNintendoDSRom } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";

export function useGameActions(getRom: () => SimpleRom | null | undefined) {
  const router = useRouter();
  const emitter = inject<Emitter<Events>>("emitter");
  const snackbar = useSnackbar();
  const collectionsStore = storeCollections();
  const romsStore = storeRoms();
  const { isFavorite, toggleFavorite } = useFavoriteToggle(emitter);

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
      snackbar.error("Failed to update status", {
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
      snackbar.error("Failed to update status", {
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
      snackbar.error(`Failed to update ${field}`, {
        icon: "mdi-alert-circle-outline",
      });
    }
  }

  const canManageCollections = computed(
    () =>
      collectionsStore.allCollections.length > 0 ||
      Boolean(collectionsStore.favoriteCollection),
  );

  const canShareQR = computed(() => {
    const rom = getRom();
    return rom ? isNintendoDSRom(rom) : false;
  });

  function play() {
    const rom = getRom();
    if (!rom) return;
    router.push(`/rom/${rom.id}/ejs`);
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
      snackbar.success("Link copied to clipboard", {
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

  return {
    isFavorited,
    canManageCollections,
    canShareQR,
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
    manageCollections,
    refreshMetadata,
    edit,
    match,
    remove,
  };
}
