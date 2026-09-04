// useRomScanRefresh: refetch the open ROM when a scan finishes, since scan
// events carry no file rows and the Files tab would keep the stale listing.
import type { ScanStats } from "@/__generated__";
import storeRoms from "@/stores/roms";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

export function useRomScanRefresh() {
  const romsStore = storeRoms();
  const { refetchCurrentRom } = useRomSync();
  const alive = useIsAlive();

  useSocketEvent<ScanStats>(
    "scan:done",
    async () => {
      const romId = romsStore.currentRom?.id;
      if (romId === undefined || !alive.value) return;
      await refetchCurrentRom(romId);
    },
    { connect: false },
  );
}
