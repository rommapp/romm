// useRomScanRefresh: refetch the open ROM when a scan finishes, since scan
// events carry no file rows and the Files tab would keep the stale listing.
import type { ScanStats } from "@/__generated__";
import { useRoute } from "vue-router";
import { useRomSync } from "@/v2/composables/useRomSync";
import { romIdFromRoute } from "@/v2/composables/useRouteRom";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

export function useRomScanRefresh() {
  const route = useRoute();
  const { refetchRom } = useRomSync();

  useSocketEvent<ScanStats>(
    "scan:done",
    async () => {
      const romId = romIdFromRoute(route);
      if (romId !== null) await refetchRom(romId);
    },
    { connect: false },
  );
}
