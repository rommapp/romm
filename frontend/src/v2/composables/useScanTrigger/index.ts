// useScanTrigger: starts per-ROM scans over the `scan` socket event. The
// RefreshMetadataDialog and the direct "Refresh files" action share it so
// the running-scan guard and the store flip behave the same in both.
import { useI18n } from "vue-i18n";
import socket from "@/services/socket";
import storeScanning from "@/stores/scanning";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import type { ScanPayload } from "@/v2/types/scan";

export function useScanTrigger() {
  const { t } = useI18n();
  const scanningStore = storeScanning();
  const snackbar = useSnackbar();

  /** Emit one `scan` event per payload, or warn and return false while a scan
   * is running: the backend rejects a second one. */
  function startScan(payloads: ScanPayload[]): boolean {
    if (scanningStore.scanning) {
      snackbar.warning(t("scan.scan-in-progress"), {
        icon: "mdi-alert-circle-outline",
      });
      return false;
    }
    scanningStore.setScanning(true);
    if (!socket.connected) socket.connect();
    for (const payload of payloads) socket.emit("scan", payload);
    return true;
  }

  return { startScan };
}
