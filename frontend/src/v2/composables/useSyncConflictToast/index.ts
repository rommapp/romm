// useSyncConflictToast: the dedupe is per page session, because a conflict is
// re-reported on every negotiation until it is resolved.
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

/** The backend's `sync:conflict` payload; socket payloads have no generated type. */
export interface SyncConflictSocketPayload {
  device_id: string;
  session_id: number;
  file_name: string;
  rom_id: number;
  rom_name: string;
  reason: string;
}

export function installSyncConflictToast(): void {
  const { t } = useI18n();
  const snackbar = useSnackbar();

  const seen = new Set<string>();

  useSocketEvent<SyncConflictSocketPayload>("sync:conflict", (payload) => {
    const key = `${payload.device_id}:${payload.rom_id}:${payload.file_name}`;
    if (seen.has(key)) return;
    seen.add(key);

    snackbar.warning(
      t("rom.save-conflict-detected", { game: payload.rom_name }),
      { icon: "mdi-content-save-alert-outline", timeout: 8000 },
    );
  });
}
