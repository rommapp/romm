import axios from "axios";

export async function fetchPlatformsApi() {
  return axios.get("/api/platforms");
}

export async function fetchRomsApi({ platform, cursor = "", size = 50, searchTerm = "" }) {
  const params = new URLSearchParams([
    ["size", size],
    ["cursor", cursor],
    ["search_term", searchTerm],
  ]);

  return axios.get(`/api/platforms/${platform}/roms`, { params });
}

export async function fetchRomApi(platform, rom) {
  return axios.get(`/api/platforms/${platform}/roms/${rom}`);
}

export async function updateRomApi(rom, updatedRom) {
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
  const params = new URLSearchParams([
    ["search_term", searchTerm],
    ["search_by", searchBy],
    ["rom", rom],
  ]);

  return axios.get("/api/search/roms/igdb", { params });
}
