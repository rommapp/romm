import type {
  AddRomsResponse,
  CursorPage_RomSchema_,
  MessageResponse,
  RomSchema,
  SearchRomSchema,
} from "@/__generated__";
import api from "@/services/api/index";
import socket from "@/services/socket";
import storeDownload from "@/stores/download";
import type { Rom } from "@/stores/roms";

export const romApi = api;

async function uploadRoms({
  platform,
  romsToUpload,
}: {
  platform: number;
  romsToUpload: File[];
}): Promise<{ data: AddRomsResponse }> {
  let formData = new FormData();
  romsToUpload.forEach((rom) => formData.append("roms", rom));

  return api.post("/roms", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { platform_id: platform },
  });
}

async function getRoms({
  platformId = null,
  size = 60,
  cursor = "",
  searchTerm = "",
  orderBy = "name",
  orderDir = "asc",
}: {
  platformId?: number | null;
  size?: number | null;
  cursor?: string | null;
  searchTerm?: string | null;
  orderBy?: string | null;
  orderDir?: string | null;
}): Promise<{ data: CursorPage_RomSchema_ }> {
  return api.get(`/roms`, {
    params: {
      platform_id: platformId,
      size: size,
      cursor: cursor,
      search_term: searchTerm,
      order_by: orderBy,
      order_dir: orderDir,
    },
  });
}

async function getRecentRoms(): Promise<{ data: CursorPage_RomSchema_ }> {
  return api.get("/roms", {
    params: { size: 15, order_by: "id", order_dir: "desc" },
  });
}

async function getRom({
  romId,
}: {
  romId: number;
}): Promise<{ data: Rom }> {
  return api.get(`/roms/${romId}`);
}

function clearRomFromDownloads({ id }: { id: number }) {
  const downloadStore = storeDownload();
  downloadStore.remove(id);

  // Disconnect socket when no more downloads are in progress
  if (downloadStore.value.length === 0) socket.disconnect();
}

async function searchRom({
  romId,
  searchTerm,
  searchBy,
  searchExtended: searchExtended,
}: {
  romId: number;
  searchTerm: string;
  searchBy: string;
  searchExtended: boolean;
}): Promise<{ data: SearchRomSchema[] }> {
  return api.get("/search/roms", {
    params: {
      rom_id: romId,
      search_term: searchTerm,
      search_by: searchBy,
      search_extended: searchExtended,
    },
  });
}

// Listen for multi-file download completion events
socket.on("download:complete", clearRomFromDownloads);

// Used only for multi-file downloads
async function downloadRom({
  rom,
  files = [],
}: {
  rom: Rom;
  files?: string[];
}) {
  // Force download of all multirom-parts when no part is selected
  if (files.length == 0) {
    files = rom.files;
  }

  var files_params = "";
  files.forEach((file) => {
    files_params += `files=${file}&`;
  });

  const a = document.createElement("a");
  a.href = `/api/roms/${rom.id}/content?${files_params}`;
  a.download = `${rom.name}.zip`;
  a.click();

  // Only connect socket if multi-file download
  if (rom.multi) {
    if (!socket.connected) socket.connect();
    storeDownload().add(rom.id);

    // Clear download state after 60 seconds in case error/timeout
    setTimeout(() => {
      clearRomFromDownloads(rom);
    }, 60 * 1000);
  }
}

export type UpdateRom = Rom & {
  artwork?: File[];
};

async function updateRom({
  rom,
  renameAsIGDB = false,
}: {
  rom: UpdateRom;
  renameAsIGDB?: boolean;
}): Promise<{ data: RomSchema }> {
  var formData = new FormData();
  if (rom.igdb_id) formData.append("igdb_id", rom.igdb_id.toString());
  if (rom.moby_id) formData.append("moby_id", rom.moby_id.toString());
  formData.append("name", rom.name || "");
  formData.append("file_name", rom.file_name);
  formData.append("summary", rom.summary || "");
  if (rom.artwork) formData.append("artwork", rom.artwork[0]);

  return api.put(`/roms/${rom.id}`, formData, {
    params: { rename_as_igdb: renameAsIGDB },
  });
}

async function deleteRoms({
  roms,
  deleteFromFs = false,
}: {
  roms: Rom[];
  deleteFromFs: boolean;
}): Promise<{ data: MessageResponse }> {
  return api.post("/roms/delete", {
    roms: roms.map((r) => r.id),
    delete_from_fs: deleteFromFs,
  });
}

export default {
  uploadRoms,
  getRoms,
  getRecentRoms,
  getRom,
  downloadRom,
  searchRom,
  updateRom,
  deleteRoms,
};
