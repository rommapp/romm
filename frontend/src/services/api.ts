import type {
  AddRomsResponse,
  CursorPage_RomSchema_,
  EnhancedRomSchema,
  MessageResponse,
  PlatformSchema,
  RomSchema,
  RomSearchResponse,
  SaveSchema,
  StateSchema,
  UserSchema,
} from "@/__generated__";
import router from "@/plugins/router";
import socket from "@/services/socket";
import storeDownload from "@/stores/download";
import type { Rom } from "@/stores/roms";
import type { User } from "@/stores/users";
import axios from "axios";

export const api = axios.create({ baseURL: "/api", timeout: 120000 });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response.status === 403) {
      router.push({
        name: "login",
        params: { next: router.currentRoute.value.path },
      });
    }
    return Promise.reject(error);
  }
);

// === Identity ===

async function login(username: string, password: string) {
  return api.post(
    "/login",
    {},
    {
      auth: {
        username: username,
        password: password,
      },
    }
  );
}

async function logout() {
  return api.post("/logout", {});
}

// === Identity ===

// === Platforms ===

async function getPlatforms(): Promise<{ data: PlatformSchema[] }> {
  return api.get("/platforms");
}

async function getPlatform(
  id: number | undefined
): Promise<{ data: PlatformSchema }> {
  return api.get(`/platforms/${id}`);
}

async function updatePlatform({
  platform,
}: {
  platform: PlatformSchema;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/platforms/${platform.id}`);
}

async function deletePlatform({
  platform,
}: {
  platform: PlatformSchema;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/platforms`, { data: { platforms: [platform.id] } });
}

// === Platforms ===

// === Roms ===

async function uploadRoms({
  platform,
  romsToUpload,
}: {
  platform: string;
  romsToUpload: File[];
}): Promise<{ data: AddRomsResponse }> {
  let formData = new FormData();
  romsToUpload.forEach((rom) => formData.append("roms", rom));

  return api.put("/roms", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { platform_slug: platform },
  });
}

async function getRoms({
  platformId,
  size = 60,
  cursor = "",
  searchTerm = "",
  orderBy = "name",
  orderDir = "asc",
}: {
  platformId: number;
  size?: number;
  cursor?: string | null;
  searchTerm?: string;
  orderBy?: string;
  orderDir?: string;
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
}): Promise<{ data: EnhancedRomSchema }> {
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
  source,
  searchTerm,
  searchBy,
}: {
  romId: number;
  source: string;
  searchTerm: string;
  searchBy: string;
}): Promise<{ data: RomSearchResponse }> {
  return api.get("/search/roms", {
    params: {
      rom_id: romId,
      source: source,
      search_term: searchTerm,
      search_by: searchBy,
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
  formData.append("igdb_id", rom.igdb_id?.toString() || "");
  formData.append("name", rom.name || "");
  formData.append("slug", rom.slug || "");
  formData.append("file_name", rom.file_name);
  formData.append("summary", rom.summary || "");
  formData.append("url_cover", rom.url_cover);
  formData.append("url_screenshots", JSON.stringify(rom.url_screenshots));
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
  return api.delete("/roms", {
    data: { roms: roms.map((r) => r.id), delete_from_fs: deleteFromFs },
  });
}

// === Roms ===

// === Users ===

async function fetchUsers(): Promise<{ data: UserSchema[] }> {
  return api.get("/users");
}

async function fetchUser(user: User): Promise<{ data: UserSchema }> {
  return api.get(`/users/${user.id}`);
}

async function fetchCurrentUser(): Promise<{ data: UserSchema | null }> {
  return api.get("/users/me");
}

async function createUser({
  username,
  password,
  role,
}: {
  username: string;
  password: string;
  role: string;
}): Promise<{ data: UserSchema }> {
  return api.post("/users", {}, { params: { username, password, role } });
}

async function updateUser({
  id,
  username,
  password,
  role,
  enabled,
  avatar,
}: {
  id: number;
  username: string;
  password: string;
  role: string;
  enabled: boolean;
  avatar?: File[];
}): Promise<{ data: UserSchema }> {
  return api.put(
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

async function deleteUser(user: User): Promise<{ data: MessageResponse }> {
  return api.delete(`/users/${user.id}`);
}

// === Users ===

// === Saves ===

async function uploadSaves({ rom, saves }: { rom: Rom; saves: File[] }) {
  let formData = new FormData();
  saves.forEach((save) => formData.append("saves", save));
  console.log(saves);
  return api.post("/saves", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function deleteSaves({
  saves,
  deleteFromFs,
}: {
  saves: SaveSchema[];
  deleteFromFs: boolean;
}) {
  return api.delete("/saves", {
    data: {
      saves: saves.map((s) => s.id),
      delete_from_fs: deleteFromFs,
    },
  });
}

// === Saves ===

// === States ===

async function uploadStates({ rom, states }: { rom: Rom; states: File[] }) {
  let formData = new FormData();
  states.forEach((state) => formData.append("states", state));

  return api.post("/states", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function deleteStates({
  states,
  deleteFromFs,
}: {
  states: StateSchema[];
  deleteFromFs: boolean;
}) {
  return api.put("/states", {
    data: {
      states: states.map((s) => s.id),
      delete_from_fs: deleteFromFs,
    },
  });
}

// === States ===

// === Config ===

async function addPlatformBindConfig({
  fsSlug,
  slug,
}: {
  fsSlug: string;
  slug: string;
}): Promise<{ data: MessageResponse }> {
  return api.post("/config/system/platforms", { fs_slug: fsSlug, slug: slug });
}

async function deletePlatformBindConfig({
  fsSlug,
}: {
  fsSlug: string;
}): Promise<{ data: MessageResponse }> {
  return api.delete("/config/system/platforms", { data: { fs_slug: fsSlug } });
}

// === Config ===

export default {
  login,
  logout,
  getPlatforms,
  getPlatform,
  deletePlatform,
  uploadRoms,
  getRoms,
  getRecentRoms,
  getRom,
  downloadRom,
  searchRom,
  updateRom,
  deleteRoms,
  createUser,
  fetchUsers,
  fetchUser,
  fetchCurrentUser,
  updateUser,
  deleteUser,
  uploadSaves,
  deleteSaves,
  uploadStates,
  deleteStates,
  addPlatformBindConfig,
  deletePlatformBindConfig,
};
