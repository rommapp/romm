// useRomScanRefresh: refetch the open ROM when a scan finishes, since scan
// events carry no file rows and the Files tab would keep the stale listing.
import type { ScanStats } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

export function useRomScanRefresh() {
  const romsStore = storeRoms();
  const { syncCachedRom } = useRomSync();
  const alive = useIsAlive();

  useSocketEvent<ScanStats>(
    "scan:done",
    async () => {
      const romId = romsStore.currentRom?.id;
      if (romId === undefined) return;
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
