import type {
  DownloadLogPage,
  DownloadSource,
  DownloadStatsOverview,
} from "@/__generated__";
import api from "@/services/api";

export interface DownloadLogQuery {
  limit?: number;
  offset?: number;
  romId?: number;
  userId?: number;
  platformId?: number;
  source?: DownloadSource;
  days?: number;
}

async function fetchOverview({
  days,
  topLimit,
}: { days?: number; topLimit?: number } = {}) {
  return api.get<DownloadStatsOverview>("/stats/downloads", {
    params: { days, top_limit: topLimit },
  });
}

async function fetchLog({
  limit,
  offset,
  romId,
  userId,
  platformId,
  source,
  days,
}: DownloadLogQuery = {}) {
  return api.get<DownloadLogPage>("/stats/downloads/log", {
    params: {
      limit,
      offset,
      rom_id: romId,
      user_id: userId,
      platform_id: platformId,
      source,
      days,
    },
  });
}

async function resyncCounters() {
  return api.post<{ roms_with_downloads: number }>("/stats/downloads/resync");
}

export default {
  fetchOverview,
  fetchLog,
  resyncCounters,
};
