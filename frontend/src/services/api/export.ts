import api from "@/services/api";

export const exportApi = api;

async function exportGamelistXml({ platformIds }: { platformIds: number[] }) {
  const params = new URLSearchParams();
  platformIds.forEach((id) => params.append("platform_ids", id.toString()));
  await api.post(`/export/gamelist-xml?${params.toString()}`);
}

async function exportPegasus({ platformIds }: { platformIds: number[] }) {
  const params = new URLSearchParams();
  platformIds.forEach((id) => params.append("platform_ids", id.toString()));
  await api.post(`/export/pegasus?${params.toString()}`);
}

// The caller's own play state, shaped for the community Backloggd importers.
async function exportBackloggdCsv() {
  return api.get<Blob>("/export/backloggd", { responseType: "blob" });
}

export default {
  exportApi,
  exportGamelistXml,
  exportPegasus,
  exportBackloggdCsv,
};
