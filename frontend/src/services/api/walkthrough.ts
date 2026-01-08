import api from "@/services/api";

export type WalkthroughFormat = "html" | "text" | "pdf";

export interface WalkthroughResponse {
  url: string;
  title?: string | null;
  author?: string | null;
  source: "GAMEFAQS" | "UPLOAD";
  format: WalkthroughFormat;
  file_path?: string | null;
  content: string;
}

export interface StoredWalkthrough {
  id: number;
  rom_id: number;
  url: string;
  title: string | null;
  author: string | null;
  source: "GAMEFAQS" | "UPLOAD";
  format: WalkthroughFormat;
  file_path: string | null;
  content: string;
  created_at: string;
  updated_at: string;
}

export async function fetchWalkthrough({
  url,
}: {
  url: string;
}): Promise<{ data: WalkthroughResponse }> {
  return api.post("/walkthroughs/fetch", { url });
}

export async function listWalkthroughsForRom(
  romId: number,
): Promise<{ data: StoredWalkthrough[] }> {
  return api.get(`/walkthroughs/roms/${romId}`);
}

export async function createWalkthroughForRom({
  romId,
  url,
}: {
  romId: number;
  url: string;
}): Promise<{ data: StoredWalkthrough }> {
  return api.post(`/walkthroughs/roms/${romId}`, { url });
}

export async function uploadWalkthroughForRom({
  romId,
  file,
  title,
  author,
}: {
  romId: number;
  file: File;
  title?: string;
  author?: string;
}): Promise<{ data: StoredWalkthrough }> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  if (author) form.append("author", author);
  return api.post(`/walkthroughs/roms/${romId}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export async function deleteWalkthrough(walkthroughId: number): Promise<void> {
  await api.delete(`/walkthroughs/${walkthroughId}`);
}

export default {
  fetchWalkthrough,
  listWalkthroughsForRom,
  createWalkthroughForRom,
  uploadWalkthroughForRom,
  deleteWalkthrough,
};
