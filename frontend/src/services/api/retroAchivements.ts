import type { RetroAchievementsGameSchema } from "@/__generated__/models/RetroAchievementsGameSchema";
import api from "@/services/api/index";

export const retroAchievementsApi = api;

async function getGameInfo({
  id,
}: {
  id: number;
}): Promise<{ data: RetroAchievementsGameSchema }> {
  return api.get(`/retroachievements/${id}`);
}

export default {
  getGameInfo,
};
