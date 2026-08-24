// useRomScanRefresh: refetch the open ROM when a scan finishes. Scan
// events never carry file rows, so after a "Refresh files" the Files tab
// would otherwise keep showing the listing from before the scan.
import type { ScanStats } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

export function useRomScanRefresh(getRomId: () => number | null) {
  const romsStore = storeRoms();
  const { syncCachedRom } = useRomSync();
  const alive = useIsAlive();

  useSocketEvent<ScanStats>(
    "scan:done",
    async () => {
      const romId = getRomId();
      if (romId === null) return;
      try {
        const { data } = await romApi.getRom({ romId });
        if (!alive.value || romsStore.currentRom?.id !== romId) return;
        romsStore.setCurrentRom(data);
        syncCachedRom(data);
      } catch (error) {
        console.error(error);
      }
    },
    { connect: false },
  );
}
