import type { MessageResponse, SearchRomSchema } from "@/__generated__";
import api from "@/services/api/index";
import socket from "@/services/socket";
import storeUpload from "@/stores/upload";
import type { DetailedRom, SimpleRom } from "@/stores/roms";
import { getDownloadLink } from "@/utils";
import type { AxiosProgressEvent } from "axios";

export const romApi = api;

async function uploadRoms({
  platformId,
  filesToUpload,
}: {
  platformId: number;
  filesToUpload: File[];
}): Promise<PromiseSettledResult<unknown>[]> {
  if (!socket.connected) socket.connect();
  const uploadStore = storeUpload();

  const promises = filesToUpload.map((file) => {
    const formData = new FormData();
    formData.append(file.name, file);

    uploadStore.start(file.name);

    return new Promise((resolve, reject) => {
      api
        .post("/roms", formData, {
          headers: {
            "Content-Type": "multipart/form-data; boundary=boundary",
            "X-Upload-Platform": platformId.toString(),
            "X-Upload-Filename": file.name,
          },
          params: {},
          onUploadProgress: (progressEvent: AxiosProgressEvent) => {
            uploadStore.update(file.name, progressEvent);
          },
        })
        .then(resolve)
        .catch((error) => {
          uploadStore.fail(file.name, error.response?.data?.detail);
          reject(error);
        });
    });
  });

  return Promise.allSettled(promises);
}

async function getRoms({
  platformId = null,
  collectionId = null,
  searchTerm = "",
  orderBy = "name",
  orderDir = "asc",
}: {
  platformId?: number | null;
  collectionId?: number | null;
  searchTerm?: string | null;
  orderBy?: string | null;
  orderDir?: string | null;
}): Promise<{ data: SimpleRom[] }> {
  return api.get(`/roms`, {
    params: {
      platform_id: platformId,
      collection_id: collectionId,
      search_term: searchTerm,
      order_by: orderBy,
      order_dir: orderDir,
    },
  });
}

async function getRecentRoms(): Promise<{ data: SimpleRom[] }> {
  return api.get("/roms", {
    params: { order_by: "id", order_dir: "desc", limit: 15 },
  });
}

async function getRom({
  romId,
}: {
  romId: number;
}): Promise<{ data: DetailedRom }> {
  return api.get(`/roms/${romId}`);
}

async function searchRom({
  romId,
  searchTerm,
  searchBy,
}: {
  romId: number;
  searchTerm: string;
  searchBy: string;
}): Promise<{ data: SearchRomSchema[] }> {
  return api.get("/search/roms", {
    params: {
      rom_id: romId,
      search_term: searchTerm,
      search_by: searchBy,
    },
  });
}

// Used only for multi-file downloads
async function downloadRom({
  rom,
  files = [],
}: {
  rom: SimpleRom;
  files?: string[];
}) {
  const a = document.createElement("a");
  a.href = getDownloadLink({ rom, files });

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export type UpdateRom = SimpleRom & {
  artwork?: File;
};

async function updateRom({
  rom,
  renameAsSource = false,
  removeCover = false,
}: {
  rom: UpdateRom;
  renameAsSource?: boolean;
  removeCover?: boolean;
}): Promise<{ data: DetailedRom }> {
  const formData = new FormData();
  if (rom.igdb_id) formData.append("igdb_id", rom.igdb_id.toString());
  if (rom.moby_id) formData.append("moby_id", rom.moby_id.toString());
  formData.append("name", rom.name || "");
  formData.append("file_name", rom.file_name);
  formData.append("summary", rom.summary || "");
  formData.append("url_cover", rom.url_cover || "");
  if (rom.artwork) formData.append("artwork", rom.artwork);

  return api.put(`/roms/${rom.id}`, formData, {
    params: {
      rename_as_source: renameAsSource,
      remove_cover: removeCover,
    },
  });
}

async function deleteRoms({
  roms,
  deleteFromFs = [],
}: {
  roms: SimpleRom[];
  deleteFromFs: number[];
}): Promise<{ data: MessageResponse }> {
  return api.post("/roms/delete", {
    roms: roms.map((r) => r.id),
    delete_from_fs: deleteFromFs,
  });
}

async function updateUserRomProps({
  romId,
  noteRawMarkdown,
  noteIsPublic,
  isMainSibling,
  completed,
}: {
  romId: number;
  noteRawMarkdown: string;
  noteIsPublic: boolean;
  isMainSibling: boolean;
  completed?: boolean;
}): Promise<{ data: DetailedRom }> {
  return api.put(`/roms/${romId}/props`, {
    note_raw_markdown: noteRawMarkdown,
    note_is_public: noteIsPublic,
    is_main_sibling: isMainSibling,
    completed,
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
  updateUserRomProps,
};
