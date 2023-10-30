import axios from "axios";
import storeDownload from "@/stores/download";
import socket from "@/services/socket";
import router from "@/plugins/router";

export const api = axios.create({ baseURL: "/api", timeout: 120000 });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response.status === 403) {
      router.push(`/login?next=${router.currentRoute.value.path}`);
    }
    return Promise.reject(error);
  }
);

export async function fetchRecentRoms() {
  return api.get("/recent");
}

export async function fetchPlatformsApi() {
  return api.get("/platforms");
}

export async function fetchRomsApi({
  platform,
  cursor = "",
  size = 60,
  searchTerm = "",
}) {
  return api.get(
    `/platforms/${platform}/roms?cursor=${cursor}&size=${size}&search_term=${searchTerm}`
  );
}

export async function fetchRomApi(platform, rom) {
  return api.get(`/platforms/${platform}/roms/${rom}`);
}

function clearRomFromDownloads({ id }) {
  const downloadStore = storeDownload();
  downloadStore.remove(id);

  // Disconnect socket when no more downloads are in progress
  if (downloadStore.value.length === 0) socket.disconnect();
}

// Listen for multi-file download completion events
socket.on("download:complete", clearRomFromDownloads);

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

export async function uploadRomsApi(romsToUpload, platform) {
  let formData = new FormData();
  romsToUpload.forEach((rom) => formData.append("roms", rom));
  return api.put(`/platforms/${platform}/roms/upload`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

export async function updateRomApi({
  id,
  r_igdb_id,
  p_slug,
  r_name,
  r_slug,
  file_name,
  summary,
  artwork,
  url_cover,
  url_screenshots,
}) {
  var formData = new FormData();
  formData.append("r_igdb_id", r_igdb_id);
  formData.append("r_name", r_name);
  formData.append("r_slug", r_slug);
  formData.append("file_name", file_name);
  formData.append("url_cover", url_cover);
  formData.append("summary", summary);
  formData.append("url_screenshots", JSON.stringify(url_screenshots));
  if (artwork) {
    formData.append("artwork", artwork[0]);
  }
  return api.patch(`/platforms/${p_slug}/roms/${id}`, formData);
}

export async function deleteRomApi(rom, deleteFromFs) {
  return api.delete(
    `/platforms/${rom.p_slug}/roms/${rom.id}?filesystem=${deleteFromFs}`
  );
}

export async function deleteRomsApi(roms, deleteFromFs) {
  return api.post(
    `/platforms/${roms[0].p_slug}/roms/delete?filesystem=${deleteFromFs}`,
    { roms: roms.map((r) => r.id) }
  );
}

export async function searchRomIGDBApi(searchTerm, searchBy, rom) {
  return api.put(
    `/search/roms/igdb?search_term=${searchTerm}&search_by=${searchBy}`,
    { rom: rom }
  );
}

export async function fetchCurrentUserApi() {
  return api.get("/users/me");
}

export async function fetchUsersApi() {
  return api.get("/users");
}

export async function fetchUserApi(user) {
  return api.get(`/users/${user.id}`);
}

export async function createUserApi({ username, password, role }) {
  return api.post("/users", {}, { params: { username, password, role } });
}

export async function updateUserApi({
  id,
  username,
  password,
  role,
  enabled,
  avatar,
}) {
  return api.patch(
    `/users/${id}`,
    {
      avatar: avatar ? avatar[0] : null,
    },
    {
      headers: {
        "Content-Type": avatar ? "multipart/form-data" : "application/json",
      },
      params: { username, password, role, enabled },
    }
  );
}

export async function deleteUserApi(user) {
  return api.delete(`/users/${user.id}`);
}
