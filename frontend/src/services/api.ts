import axios from "axios";
import storeDownload from "@/stores/download";
import socket from "@/services/socket";
import router from "@/plugins/router";
import type { Rom } from "@/stores/roms";
import type { User } from "@/stores/users";

import type {
  PlatformSchema,
  DeletePlatformResponse,
  RomSchema,
  EnhancedRomSchema,
  UploadRomResponse,
  DeleteRomResponse,
  MassDeleteRomResponse,
  RomSearchResponse,
  UserSchema,
  MessageResponse,
  CursorPage_RomSchema_,
  SaveSchema,
  StateSchema,
} from "@/__generated__";

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

async function fetchPlatforms(): Promise<{ data: PlatformSchema[] }> {
  return api.get("/platforms");
}

async function deletePlatform({
  platform,
  deleteFromFs = false,
}: {
  platform: PlatformSchema;
  deleteFromFs: boolean;
}): Promise<{ data: DeletePlatformResponse }> {
  return api.delete(`/platforms/${platform.fs_slug}`, {
    params: { delete_from_fs: deleteFromFs },
  });
}

async function fetchRecentRoms(): Promise<{ data: RomSchema[] }> {
  return api.get("/roms-recent");
}

async function fetchRoms({
  platform,
  cursor = "",
  size = 60,
  searchTerm = "",
}: {
  platform: string;
  cursor?: string | null;
  size?: number;
  searchTerm?: string;
}): Promise<{ data: CursorPage_RomSchema_ }> {
  return api.get(`/platforms/${platform}/roms`, {
    params: { cursor, size, search_term: searchTerm },
  });
}

async function fetchRom({
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
  a.href = `/api/roms/${rom.id}/download?${files_params}`;
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

async function uploadRoms({
  platform,
  romsToUpload,
}: {
  platform: string;
  romsToUpload: File[];
}): Promise<{ data: UploadRomResponse }> {
  let formData = new FormData();
  romsToUpload.forEach((rom) => formData.append("roms", rom));

  return api.put("/roms/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { platform_slug: platform },
  });
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

  return api.patch(`/roms/${rom.id}`, formData, {
    params: { rename_as_igdb: renameAsIGDB },
  });
}

async function deleteRom({
  rom,
  deleteFromFs = false,
}: {
  rom: Rom;
  deleteFromFs: boolean;
}): Promise<{ data: DeleteRomResponse }> {
  return api.delete(`/roms/${rom.id}`, {
    params: { delete_from_fs: deleteFromFs },
  });
}

async function deleteRoms({
  roms,
  deleteFromFs = false,
}: {
  roms: Rom[];
  deleteFromFs: boolean;
}): Promise<{ data: MassDeleteRomResponse }> {
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

async function searchIGDB({
  romId,
  query,
  field,
}: {
  romId: number;
  query: string;
  field: string;
}): Promise<{ data: RomSearchResponse }> {
  return api.put(
    "/search/roms/igdb",
    {},
    { params: { rom_id: romId, query, field } }
  );
}

async function fetchCurrentUser(): Promise<{ data: UserSchema | null }> {
  return api.get("/users/me");
}

async function fetchUsers(): Promise<{ data: UserSchema[] }> {
  return api.get("/users");
}

async function fetchUser(user: User): Promise<{ data: UserSchema }> {
  return api.get(`/users/${user.id}`);
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

async function deleteUser(user: User): Promise<{ data: MessageResponse }> {
  return api.delete(`/users/${user.id}`);
}

async function uploadSaves({ rom, saves }: { rom: Rom; saves: File[] }) {
  let formData = new FormData();
  saves.forEach((save) => formData.append("saves", save));

  return api.put("/saves/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function deleteSaves({ saves }: { saves: SaveSchema[] }) {
  return api.post("/saves/delete", {
    saves: saves.map((s) => s.id),
  });
}

async function uploadStates({ rom, states }: { rom: Rom; states: File[] }) {
  let formData = new FormData();
  states.forEach((state) => formData.append("states", state));

  return api.put("/states/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { rom_id: rom.id },
  });
}

async function deleteStates({ states }: { states: StateSchema[] }) {
  return api.post("/states/delete", {
    states: states.map((s) => s.id),
  });
}

export default {
  fetchPlatforms,
  deletePlatform,
  fetchRecentRoms,
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
  uploadSaves,
  deleteSaves,
  uploadStates,
  deleteStates,
};
