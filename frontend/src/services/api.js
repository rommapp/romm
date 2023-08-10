import axios from "axios";
import useDownloadStore from "@/stores/download.js";
import socket from "@/services/socket.js";

export async function fetchPlatformsApi() {
  return axios.get("/api/platforms");
}

export async function fetchRomsApi({
  platform,
  cursor = "",
  size = 60,
  searchTerm = "",
}) {
  return axios.get(
    `/api/platforms/${platform}/roms?cursor=${cursor}&size=${size}&search_term=${searchTerm}`
  );
}

export async function fetchRomApi(platform, rom) {
  return axios.get(`/api/platforms/${platform}/roms/${rom}`);
}

// Listen for multi-file download events
socket.on("download:complete", ({ id }) => {
  const downloadStore = useDownloadStore();
  useDownloadStore().remove(id);
  if (downloadStore.value.length === 0) socket.disconnect();
});

// Used only for multi-file downloads
export async function downloadRomApi(rom, files) {
  // Force download of all multirom-parts when no part is selected
  if (files != undefined && files.length == 0) {
    files = undefined;
  }

  const a = document.createElement("a");
  a.href = `/api/platforms/${rom.p_slug}/roms/${rom.id}/download?files=${
    files || rom.files
  }`;
  a.download = `${rom.r_name}.zip`;
  a.click();

  if (!socket.connected) socket.connect();
  useDownloadStore().add(rom.id);
}

export async function updateRomApi(rom, updatedData, renameAsIGDB) {
  const updatedRom = {
    r_igdb_id: updatedData.r_igdb_id,
    r_slug: updatedData.r_slug,
    summary: updatedData.summary,
    url_cover: updatedData.url_cover,
    url_screenshots: updatedData.url_screenshots,
    r_name: updatedData.r_name,
    file_name: renameAsIGDB
      ? rom.file_name.replace(rom.file_name_no_tags, updatedData.r_name)
      : updatedData.file_name,
  };
  return axios.patch(`/api/platforms/${rom.p_slug}/roms/${rom.id}`, {
    updatedRom,
  });
}

export async function deleteRomApi(rom, deleteFromFs) {
  return axios.delete(
    `/api/platforms/${rom.p_slug}/roms/${rom.id}?filesystem=${deleteFromFs}`
  );
}

export async function searchRomIGDBApi(searchTerm, searchBy, rom) {
  return axios.put(
    `/api/search/roms/igdb?search_term=${searchTerm}&search_by=${searchBy}`,
    { rom: rom }
  );
}
