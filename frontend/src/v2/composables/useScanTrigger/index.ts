// useScanTrigger: starts scans over the `scan` socket event, so every caller
// refuses a second one the same way while a scan is running.
import { useI18n } from "vue-i18n";
import socket from "@/services/socket";
import storeScanning from "@/stores/scanning";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import type { ScanRequest } from "@/v2/types/scan";

export function useScanTrigger() {
  const { t } = useI18n();
  const scanningStore = storeScanning();
  const snackbar = useSnackbar();

  /** Emit one `scan` event per request, or warn and return false while a scan
   * is running: the backend rejects a second one. */
  function startScan(requests: ScanRequest[]): boolean {
    if (scanningStore.scanning) {
      snackbar.warning(t("scan.scan-in-progress"), {
        icon: "mdi-alert-circle-outline",
      });
      return false;
    }
    scanningStore.setScanning(true);
    if (!socket.connected) socket.connect();
    for (const request of requests) socket.emit("scan", request);
    return true;
  }

  return { startScan };
}
