import api from "@/services/api";

export const gamelistApi = api;

async function exportGamelist({
  platformIds,
}: {
  platformIds: number[];
}): Promise<void> {
  const params = new URLSearchParams();
  platformIds.forEach((id) => params.append("platform_ids", id.toString()));
  await api.post(`/gamelist/export?${params.toString()}`);
}

export default {
  exportGamelist,
};
