// useSyncConflictToast: the dedupe is per page session, because a conflict is
// re-reported on every negotiation until it is resolved.
import { useI18n } from "vue-i18n";
import storeRoms from "@/stores/roms";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

/** The backend's `sync:conflict` payload; socket payloads have no generated type. */
export interface SyncConflictSocketPayload {
  device_id: string;
  session_id: number;
  file_name: string;
  rom_id: number;
  reason: string;
}

export function installSyncConflictToast(): void {
  const { t } = useI18n();
  const snackbar = useSnackbar();
  const romsStore = storeRoms();
  const galleryRomsStore = storeGalleryRoms();

  const seen = new Set<string>();

  /** The ROM's display name, or null when no loaded cache holds the game. */
  function romName(romId: number): string | null {
    const rom =
      galleryRomsStore.getRomById(romId) ??
      (romsStore.currentRom?.id === romId ? romsStore.currentRom : null) ??
      romsStore.recentRoms.find((recent) => recent.id === romId);
    return rom ? rom.name || rom.fs_name : null;
  }

  useSocketEvent<SyncConflictSocketPayload>("sync:conflict", (payload) => {
    const key = `${payload.device_id}:${payload.rom_id}:${payload.file_name}`;
    if (seen.has(key)) return;
    seen.add(key);

    const name = romName(payload.rom_id);
    snackbar.warning(
      name
        ? t("rom.save-conflict-detected", { game: name })
        : t("rom.save-conflict-detected-unknown-game"),
      { icon: "mdi-content-save-alert-outline", timeout: 8000 },
    );
  });
}
