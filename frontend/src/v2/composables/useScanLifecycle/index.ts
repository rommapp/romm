// useScanLifecycle — global wire-up between the scan socket events and the
// `scanning` Pinia store. Mounted once at the top of the v2 tree (AppLayout)
// so the navbar's ScanningIndicator, the dedicated /scan view, and anyone
// else reading `scanning` / `scanningPlatforms` / `scanStats` always see
// the same truth — even when the user navigates between routes mid-scan.
//
// Events handled:
//   * `scan:scanning_platform` — backend announces the platform it's about
//                                to process; push it onto the live log so
//                                the /scan view can render a panel for it.
//   * `scan:scanning_rom`      — per-ROM update during a scan. Batched on
//                                a 100ms debounce window so a thousand
//                                rapid-fire updates don't tank rendering.
//   * `scan:update_stats`      — periodic progress; keep `scanStats` fresh.
//   * `scan:done`              — scan finished; persist the final stats,
//                                flip `scanning` off so the indicator hides,
//                                then refetch platforms to reconcile counts.
//   * `scan:done_ko`           — scan errored; surface the message as a
//                                snackbar and flip `scanning` off.
//
// Events alone can't tell a tab that loads mid-scan what's going on, so
// install also reconciles against the running RQ job — see
// `reconcileWithRunningScan` below.
//
// `useSocketEvent` is the typed subscription wrapper that auto-cleans up
// on unmount; since AppLayout never unmounts during normal use the
// listeners effectively live for the session.
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { inject, watch } from "vue";
import type { ScanStats, ScanTaskStatusResponse } from "@/__generated__";
import platformApi from "@/services/api/platform";
import taskApi from "@/services/api/task";
import storeAuth from "@/stores/auth";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning, { type ScanningPlatform } from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

export function installScanLifecycle() {
  const scanningStore = storeScanning();
  const romsStore = storeRoms();
  const collectionsStore = storeCollections();
  const platformsStore = storePlatforms();
  const galleryRomsStore = storeGalleryRoms();
  const authStore = storeAuth();
  const emitter = inject<Emitter<Events>>("emitter");

  useSocketEvent<ScanningPlatform>(
    "scan:scanning_platform",
    ({
      name,
      display_name,
      slug,
      id,
      fs_slug,
      is_identified,
      new_firmware_count,
    }) => {
      scanningStore.setScanning(true);
      // De-dupe by display_name so a re-scan of the same platform
      // doesn't render two panels for it.
      scanningStore.scanningPlatforms = scanningStore.scanningPlatforms.filter(
        (p) => p.display_name !== display_name,
      );
      // Prepend so the platform being scanned right now stays at the top of
      // the live log — no scrolling to follow progress.
      scanningStore.scanningPlatforms.unshift({
        name,
        display_name,
        slug,
        id,
        fs_slug,
        roms: [],
        new_firmware_count,
        is_identified,
      });

      // Surface brand-new platforms in the canonical platforms store the
      // moment the scan reaches them — previously they only appeared after
      // a manual page refresh. The socket payload is a partial (8 fields),
      // so fetch the full PlatformSchema before adding it to the store.
      if (!platformsStore.has(id)) {
        platformApi
          .getPlatform(id)
          .then(({ data }) => {
            if (!platformsStore.has(data.id)) platformsStore.add(data);
          })
          .catch((error) => console.error(error));
      }
    },
  );

  // Batch per-ROM updates so a fast scan doesn't trigger one render per
  // ROM. Queue drains every 100ms; matches the v1 behavior. Stored
  // outside the handler so multiple events share the same queue + flush.
  const romUpdateQueue: SimpleRom[] = [];
  const refreshGallery = debounce(
    () => {
      galleryRomsStore.invalidateWindows();
      void galleryRomsStore.fetchInitialMetadata();
    },
    250,
    { maxWait: 1000 },
  );
  const processRomUpdates = debounce(() => {
    if (romUpdateQueue.length === 0) return;
    const updates = romUpdateQueue.splice(0, romUpdateQueue.length);
    updates.forEach((rom) => {
      // Keep the global "recent" list fresh so any view watching it
      // (Home) reflects the new ROM at the top.
      romsStore.removeFromRecent(rom);
      romsStore.addToRecent(rom);

      // If the user is currently looking at the gallery of the platform
      // being scanned, refresh from the server to preserve sorting/filtering.
      if (galleryRomsStore.currentPlatform?.id === rom.platform_id) {
        refreshGallery();
      }
      if (romsStore.currentPlatform?.id === rom.platform_id) {
        const existing = romsStore.filteredRoms.find((r) => r.id === rom.id);
        if (existing) romsStore.update(rom);
        else romsStore.add([rom]);
      }

      let scannedPlatform = scanningStore.scanningPlatforms.find(
        (p) => p.fs_slug === rom.platform_fs_slug,
      );

      // Socket may have dropped the `scan:scanning_platform` event — add
      // the platform synthetically so the user still sees something.
      if (!scannedPlatform) {
        scanningStore.scanningPlatforms.unshift({
          name: rom.platform_display_name,
          display_name: rom.platform_display_name,
          slug: rom.platform_slug,
          id: rom.platform_id,
          fs_slug: rom.platform_fs_slug,
          is_identified: true,
          roms: [],
          new_firmware_count: 0,
        });
        scannedPlatform = scanningStore.scanningPlatforms.at(0)!;
      }

      const existingInPlatform = scannedPlatform.roms.find(
        (r) => r.id === rom.id,
      );
      if (existingInPlatform) {
        scannedPlatform.roms = scannedPlatform.roms.map((r) =>
          r.id === rom.id ? rom : r,
        );
      } else {
        // Newest ROM first, same as platforms — most recent stays on top.
        scannedPlatform.roms.unshift(rom);
        // Keep the canonical platforms store's count live for genuinely new
        // ROMs: the gallery/nav getters gate on `rom_count > 0`, so this is
        // what makes a freshly-scanned platform actually render mid-scan.
        const storePlatform = platformsStore.get(rom.platform_id);
        if (storePlatform) storePlatform.rom_count += 1;
      }
    });
  }, 100);

  useSocketEvent<SimpleRom>("scan:scanning_rom", (rom) => {
    scanningStore.setScanning(true);
    romUpdateQueue.push(rom);
    processRomUpdates();
  });

  // Stats are the only event a scan emits continuously: `scanning_platform`
  // fires once per platform, and `scanning_rom` only for ROMs the scan adds or
  // changes, so a scan over a settled library can go a long while emitting
  // nothing else. Flipping `scanning` here is what lets a tab that missed the
  // start of the scan catch up on the next tick.
  useSocketEvent<ScanStats>("scan:update_stats", (stats) => {
    scanningStore.setScanning(true);
    scanningStore.setScanStats(stats);
  });

  useSocketEvent<ScanStats>("scan:done", (stats) => {
    markScanEnded();
    scanningStore.setScanStats(stats);
    scanningStore.setScanning(false);
    // Reconcile against the backend once the scan settles: pick up anything
    // the live updates missed and correct rom_counts that drifted.
    void platformsStore.fetchPlatforms();
    void collectionsStore.refreshVirtualCollections();
    emitter?.emit("snackbarShow", {
      msg: "Scan completed successfully.",
      color: "success",
      icon: "mdi-check-bold",
      timeout: 4000,
    });
  });

  useSocketEvent<string>("scan:done_ko", (msg) => {
    markScanEnded();
    scanningStore.setScanning(false);
    emitter?.emit("snackbarShow", {
      msg: `Scan failed: ${msg}`,
      color: "error",
      icon: "mdi-close-circle",
      timeout: 6000,
    });
  });

  // Reconcile with the scan the server is actually running. Without this a
  // tab that loads mid-scan (refresh, second tab, another device) shows the
  // /scan empty state and an armed "Start scan" button until an event lands.
  //
  // `/tasks/status` needs `tasks.run`, the same scope the `scan` socket
  // handler gates on, so anyone who could have started this scan can read it
  // back. Users without it stay purely event-driven.
  let sawScanEnd = false;
  function markScanEnded() {
    sawScanEnd = true;
  }

  // Reconciles once per eligible user: collapsing the source to an id keeps
  // unrelated profile updates from re-firing it, and re-arms if the scope
  // shows up later.
  watch(
    () =>
      authStore.user?.oauth_scopes.includes("tasks.run")
        ? authStore.user.id
        : null,
    (userId) => {
      if (userId === null) return;
      sawScanEnd = false;
      reconcileWithRunningScan();
    },
    { immediate: true },
  );

  function reconcileWithRunningScan() {
    taskApi
      .getTaskStatus()
      .then(({ data }) => {
        // A terminal event that landed while the request was in flight means
        // the job we asked about is already over; don't resurrect it. Same for
        // stats already streaming in, which are fresher than the job's meta.
        if (sawScanEnd || scanningStore.scanning) return;
        const running = data.find(
          (task): task is ScanTaskStatusResponse =>
            task.task_type === "scan" && task.status === "started",
        );
        if (!running) return;
        scanningStore.setScanning(true);
        // The per-platform live log only ever lived in the originating tab's
        // memory, so the panel list fills in from the next platform onward.
        // `meta` is typed as required but this is a JSON boundary: a missing
        // snapshot just means no counters yet, not "no scan".
        if (running.meta?.scan_stats)
          scanningStore.setScanStats(running.meta.scan_stats);
      })
      .catch((error) => console.error(error));
  }
}
