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
// `useSocketEvent` is the typed subscription wrapper that auto-cleans up
// on unmount; since AppLayout never unmounts during normal use the
// listeners effectively live for the session.
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { inject } from "vue";
import type { ScanStats } from "@/__generated__";
import platformApi from "@/services/api/platform";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning, { type ScanningPlatform } from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

export function installScanLifecycle() {
  const scanningStore = storeScanning();
  const romsStore = storeRoms();
  const platformsStore = storePlatforms();
  const galleryRomsStore = storeGalleryRoms();
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
      firmware_count,
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
        firmware_count,
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
  const processRomUpdates = debounce(() => {
    if (romUpdateQueue.length === 0) return;
    const updates = romUpdateQueue.splice(0, romUpdateQueue.length);
    updates.forEach((rom) => {
      // Keep the global "recent" list fresh so any view watching it
      // (Home) reflects the new ROM at the top.
      romsStore.removeFromRecent(rom);
      romsStore.addToRecent(rom);

      // If the user is currently looking at the gallery of the platform
      // being scanned, fold the new ROM into the visible list.
      if (galleryRomsStore.currentPlatform?.id === rom.platform_id) {
        galleryRomsStore.addLiveRom(rom);
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
          firmware_count: 0,
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

  useSocketEvent<ScanStats>("scan:update_stats", (stats) => {
    scanningStore.setScanStats(stats);
  });

  useSocketEvent<ScanStats>("scan:done", (stats) => {
    scanningStore.setScanStats(stats);
    scanningStore.setScanning(false);
    // Reconcile against the backend once the scan settles: pick up anything
    // the live updates missed and correct rom_counts that drifted.
    void platformsStore.fetchPlatforms();
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
