import type { SearchCoverSchema } from "@/__generated__";
import api from "@/services/api/index";

export const retroAchievementsApi = api;

async function getGameInfo({
  id,
}: {
  id: number;
}): Promise<{ data: SearchCoverSchema[] }> {
  return api.get(`/retroachievements/${id}`);
}

export default {
  getGameInfo,
};
