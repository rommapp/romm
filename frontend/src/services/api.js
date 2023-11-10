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
  return api.get("/roms-recent");
}

async function fetchPlatforms() {
  return api.get("/platforms");
}

async function fetchRoms({
  platform,
  cursor = "",
  size = 60,
  searchTerm = "",
}) {
  return api.get(`/platforms/${platform}/roms`, {
    params: { cursor, size, searchTerm },
  });
}

async function fetchRom({ romId }) {
  return api.get(`/roms/${romId}`);
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
async function downloadRom({ rom, files = [] }) {
  // Force download of all multirom-parts when no part is selected
  if (files != undefined && files.length == 0) {
    files = undefined;
  }

  const a = document.createElement("a");
  a.href = `/api/roms/${rom.id}/download?files=${files}`;
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

async function uploadRoms({ platform, romsToUpload }) {
  let formData = new FormData();
  romsToUpload.forEach((rom) => formData.append("roms", rom));

  return api.put("/roms/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { platform_slug: platform },
  });
}

async function updateRom({ rom, renameAsIGDB = false }) {
  var formData = new FormData();
  formData.append("igdb_id", rom.igdb_id || "");
  formData.append("name", rom.name);
  formData.append("slug", rom.slug);
  formData.append("file_name", rom.file_name);
  formData.append("summary", rom.summary);
  formData.append("url_cover", rom.url_cover);
  formData.append("url_screenshots", JSON.stringify(rom.url_screenshots));
  if (rom.artwork) formData.append("artwork", rom.artwork[0]);

  return api.patch(`/roms/${rom.id}`, formData, {
    params: { rename_as_igdb: renameAsIGDB },
  });
}

async function deleteRom({ rom, deleteFromFs = false }) {
  return api.delete(`/roms/${rom.id}`, {
    params: { delete_from_fs: deleteFromFs },
  });
}

async function deleteRoms({ roms, deleteFromFs = false }) {
  return api.post(
    "/roms/delete",
    {
      roms: roms.map((r) => r.id),
    },
    {
      params: { delete_from_fs: deleteFromFs },
    }
  );
}

async function searchIGDB({ romId, query, field }) {
  return api.put(
    "/search/roms/igdb",
    {},
    { params: { rom_id: romId, query, field } }
  );
}

async function fetchCurrentUser() {
  return api.get("/users/me");
}

async function fetchUsers() {
  return api.get("/users");
}

async function fetchUser(user) {
  return api.get(`/users/${user.id}`);
}

async function createUser({ username, password, role }) {
  return api.post("/users", {}, { params: { username, password, role } });
}

async function updateUser({ id, username, password, role, enabled, avatar }) {
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

async function deleteUser(user) {
  return api.delete(`/users/${user.id}`);
}

export default {
  fetchPlatforms,
  fetchRoms,
  fetchRom,
  downloadRom,
  uploadRoms,
  updateRom,
  deleteRom,
  deleteRoms,
  searchIGDB,
  fetchCurrentUser,
  fetchUsers,
  fetchUser,
  createUser,
  updateUser,
  deleteUser,
};
