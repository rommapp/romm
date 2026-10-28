// useRomScanRefresh: refetch the open ROM when a scan finishes, since scan
// events carry no file rows and the Files tab would keep the stale listing.
import { useRoute } from "vue-router";
import type { ScanStats } from "@/__generated__";
import { useRomSync } from "@/composables/useRomSync";
import { romIdFromRoute } from "@/composables/useRouteRom";
import { useSocketEvent } from "@/composables/useSocketEvent";

export function useRomScanRefresh() {
  const route = useRoute();
  const { refetchRom } = useRomSync();

  async function refresh() {
    const romId = romIdFromRoute(route);
    if (romId !== null) await refetchRom(romId);
  }

  useSocketEvent<ScanStats>("scan:done", () => void refresh(), {
    connect: false,
  });
}
