// useScanLifecycle — global wire-up between the scan socket events and the
// `scanning` Pinia store. Mounted once at the top of the v2 tree (AppLayout)
// so the navbar's ScanningIndicator, the dedicated /scan view, and anyone
// else reading `scanning` / `scanStats` always see the same truth — even
// when the user navigates between routes mid-scan.
//
// Events handled:
//   * `scan:update_stats` — periodic progress; keep `scanStats` fresh.
//   * `scan:done`         — scan finished; persist the final stats then
//                           flip `scanning` off so the indicator hides.
//   * `scan:done_ko`      — scan errored; surface the message as a
//                           snackbar and flip `scanning` off.
//
// `useSocketEvent` is the typed subscription wrapper that auto-cleans up
// on unmount; since AppLayout never unmounts during normal use the
// listeners effectively live for the session.
import type { Emitter } from "mitt";
import { inject } from "vue";
import type { ScanStats } from "@/__generated__";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

export function installScanLifecycle() {
  const scanningStore = storeScanning();
  const emitter = inject<Emitter<Events>>("emitter");

  useSocketEvent<ScanStats>("scan:update_stats", (stats) => {
    scanningStore.setScanStats(stats);
  });

  useSocketEvent<ScanStats>("scan:done", (stats) => {
    scanningStore.setScanStats(stats);
    scanningStore.setScanning(false);
    emitter?.emit("snackbarShow", {
      msg: "Scan completed successfully.",
      color: "success",
      icon: "mdi-check-bold",
      timeout: 4000,
    });
  });

  useSocketEvent<string>("scan:done_ko", (msg) => {
    scanningStore.setScanning(false);
    emitter?.emit("snackbarShow", {
      msg: `Scan failed: ${msg}`,
      color: "error",
      icon: "mdi-close-circle",
      timeout: 6000,
    });
  });
}
