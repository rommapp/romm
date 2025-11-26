import type { AxiosProgressEvent } from "axios";
import type {
  BulkOperationResponse,
  RomUserSchema,
  UserNoteSchema,
} from "@/__generated__";
import { type CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import api from "@/services/api";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import type { DetailedRom, SimpleRom, SearchRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import { getDownloadPath, getStatusKeyForText } from "@/utils";

export const romApi = api;

const DOWNLOAD_CLEANUP_DELAY = 100;

async function uploadRoms({
  platformId,
  filesToUpload,
}: {
  platformId: number;
  filesToUpload: File[];
}): Promise<PromiseSettledResult<null>[]> {
  const heartbeat = storeHeartbeat();

  if (!socket.connected) socket.connect();
  const uploadStore = storeUpload();

  const promises = filesToUpload.map((file) => {
    const formData = new FormData();
    formData.append(file.name, file);

    uploadStore.start(file.name);
    return new Promise<null>((resolve, reject) => {
      api
        .post("/roms", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
            "X-Upload-Platform": platformId.toString(),
            "X-Upload-Filename": file.name,
          },
          timeout: heartbeat.value.FRONTEND.UPLOAD_TIMEOUT * 1000,
          params: {},
          onUploadProgress: (progressEvent: AxiosProgressEvent) => {
            uploadStore.update(file.name, progressEvent);
          },
        })
        .then(() => {
          resolve(null);
        })
        .catch((error) => {
          uploadStore.fail(file.name, error.response?.data?.detail);
          reject(error);
        });
    });
  });

  return Promise.allSettled(promises);
}

export interface GetRomsParams {
  platformId?: number | null;
  collectionId?: number | null;
  virtualCollectionId?: string | null;
  smartCollectionId?: number | null;
  searchTerm?: string | null;
  limit?: number;
  offset?: number;
  orderBy?: string | null;
  orderDir?: string | null;
  filterUnmatched?: boolean;
  filterMatched?: boolean;
  filterFavorites?: boolean;
  filterDuplicates?: boolean;
  filterPlayables?: boolean;
  filterRA?: boolean;
  filterMissing?: boolean;
  filterVerified?: boolean;
  groupByMetaId?: boolean;
  selectedGenre?: string | null;
  selectedFranchise?: string | null;
  selectedCollection?: string | null;
  selectedCompany?: string | null;
  selectedAgeRating?: string | null;
  selectedStatus?: string | null;
  selectedRegion?: string | null;
  selectedLanguage?: string | null;
}

async function getRoms({
  platformId = null,
  collectionId = null,
  virtualCollectionId = null,
  smartCollectionId = null,
  searchTerm = null,
  limit = 72,
  offset = 0,
  orderBy = "name",
  orderDir = "asc",
  filterUnmatched = false,
  filterMatched = false,
  filterFavorites = false,
  filterDuplicates = false,
  filterPlayables = false,
  filterRA = false,
  filterMissing = false,
  filterVerified = false,
  groupByMetaId = false,
  selectedGenre = null,
  selectedFranchise = null,
  selectedCollection = null,
  selectedCompany = null,
  selectedAgeRating = null,
  selectedStatus = null,
  selectedRegion = null,
  selectedLanguage = null,
}: GetRomsParams): Promise<{ data: GetRomsResponse }> {
  return api.get(`/roms`, {
    params: {
      platform_id: platformId,
      collection_id: collectionId,
      virtual_collection_id: virtualCollectionId,
      smart_collection_id: smartCollectionId,
      search_term: searchTerm,
      limit: limit,
      offset: offset,
      order_by: orderBy,
      order_dir: orderDir,
      group_by_meta_id: groupByMetaId,
      selected_genre: selectedGenre,
      selected_franchise: selectedFranchise,
      selected_collection: selectedCollection,
      selected_company: selectedCompany,
      selected_age_rating: selectedAgeRating,
      selected_status: getStatusKeyForText(selectedStatus),
      selected_region: selectedRegion,
      selected_language: selectedLanguage,
      ...(filterUnmatched ? { matched: false } : {}),
      ...(filterMatched ? { matched: true } : {}),
      ...(filterFavorites ? { favorite: true } : {}),
      ...(filterDuplicates ? { duplicate: true } : {}),
      ...(filterPlayables ? { playable: true } : {}),
      ...(filterMissing ? { missing: true } : {}),
      ...(filterRA ? { has_ra: true } : {}),
      ...(filterVerified ? { verified: true } : {}),
    },
  });
}

export const RECENT_ROMS_LIMIT = 15;
export const RECENT_PLAYED_ROMS_LIMIT = 15;

async function getRecentRoms(): Promise<{ data: GetRomsResponse }> {
  return api.get("/roms", {
    params: {
      order_by: "id",
      order_dir: "desc",
      limit: RECENT_ROMS_LIMIT,
      with_char_index: false,
    },
  });
}

async function getRecentPlayedRoms(): Promise<{ data: GetRomsResponse }> {
  return api.get("/roms", {
    params: {
      order_by: "last_played",
      order_dir: "desc",
      limit: RECENT_PLAYED_ROMS_LIMIT,
      with_char_index: false,
    },
  });
}

async function getRom({
  romId,
}: {
  romId: number;
}): Promise<{ data: DetailedRom }> {
  return api.get(`/roms/${romId}`);
}

async function getRomByMetadataProvider({
  provider,
  id,
}: {
  provider: string;
  id: number;
}): Promise<{ data: DetailedRom }> {
  const params = { [provider]: id };
  return api.get(`/roms/by-metadata-provider/`, {
    params,
  });
}

async function searchRom({
  romId,
  searchTerm,
  searchBy,
}: {
  romId: number;
  searchTerm: string;
  searchBy: string;
}): Promise<{ data: SearchRom[] }> {
  return api.get("/search/roms", {
    params: {
      rom_id: romId,
      search_term: searchTerm,
      search_by: searchBy,
    },
  });
}

async function downloadRom({
  rom,
  fileIDs = [],
}: {
  rom: SimpleRom;
  fileIDs?: number[];
}) {
  return new Promise<void>((resolve) => {
    const a = document.createElement("a");
    a.href = getDownloadPath({ rom, fileIDs });
    a.style.display = "none";

    document.body.appendChild(a);
    a.click();

    setTimeout(() => {
      document.body.removeChild(a);
      resolve();
    }, DOWNLOAD_CLEANUP_DELAY);
  });
}

async function bulkDownloadRoms({
  roms,
  filename,
}: {
  roms: SimpleRom[];
  filename?: string;
}) {
  return new Promise<void>((resolve) => {
    if (roms.length === 0) return resolve();

    const romIds = roms.map((rom) => rom.id);

    const queryParams = new URLSearchParams();
    queryParams.append("rom_ids", romIds.join(","));
    if (filename) queryParams.append("filename", filename);

    const a = document.createElement("a");
    a.href = `/api/roms/download?${queryParams.toString()}`;
    a.style.display = "none";

    document.body.appendChild(a);
    a.click();

    setTimeout(() => {
      document.body.removeChild(a);
      resolve();
    }, DOWNLOAD_CLEANUP_DELAY);
  });
}

export type UpdateRom = SimpleRom & {
  artwork?: File;
  raw_metadata?: {
    igdb_metadata?: string;
    moby_metadata?: string;
    ss_metadata?: string;
    launchbox_metadata?: string;
    hasheous_metadata?: string;
    flashpoint_metadata?: string;
    hltb_metadata?: string;
  };
};

async function updateRom({
  rom,
  removeCover = false,
  unmatch = false,
}: {
  rom: UpdateRom;
  removeCover?: boolean;
  unmatch?: boolean;
}): Promise<{ data: DetailedRom }> {
  const formData = new FormData();
  formData.append("name", rom.name || "");
  formData.append("fs_name", rom.fs_name);
  formData.append("summary", rom.summary || "");

  formData.append("igdb_id", rom.igdb_id?.toString() || "");
  formData.append("sgdb_id", rom.sgdb_id?.toString() || "");
  formData.append("moby_id", rom.moby_id?.toString() || "");
  formData.append("ss_id", rom.ss_id?.toString() || "");
  formData.append("launchbox_id", rom.launchbox_id?.toString() || "");
  formData.append("ra_id", rom.ra_id?.toString() || "");
  formData.append("flashpoint_id", rom.flashpoint_id?.toString() || "");
  formData.append("hasheous_id", rom.hasheous_id?.toString() || "");
  formData.append("tgdb_id", rom.tgdb_id?.toString() || "");
  formData.append("hltb_id", rom.hltb_id?.toString() || "");

  if (rom.raw_metadata?.igdb_metadata) {
    formData.append("raw_igdb_metadata", rom.raw_metadata.igdb_metadata);
  }
  if (rom.raw_metadata?.moby_metadata) {
    formData.append("raw_moby_metadata", rom.raw_metadata.moby_metadata);
  }
  if (rom.raw_metadata?.ss_metadata) {
    formData.append("raw_ss_metadata", rom.raw_metadata.ss_metadata);
  }
  if (rom.raw_metadata?.launchbox_metadata) {
    formData.append(
      "raw_launchbox_metadata",
      rom.raw_metadata.launchbox_metadata,
    );
  }
  if (rom.raw_metadata?.hasheous_metadata) {
    formData.append(
      "raw_hasheous_metadata",
      rom.raw_metadata.hasheous_metadata,
    );
  }
  if (rom.raw_metadata?.flashpoint_metadata) {
    formData.append(
      "raw_flashpoint_metadata",
      rom.raw_metadata.flashpoint_metadata,
    );
  }
  if (rom.raw_metadata?.hltb_metadata) {
    formData.append("raw_hltb_metadata", rom.raw_metadata.hltb_metadata);
  }

  // Don't set url_cover on manual artwork upload
  if (rom.artwork) {
    formData.append("artwork", rom.artwork);
  } else {
    formData.append("url_cover", rom.url_cover || "");
  }

  return api.put(`/roms/${rom.id}`, formData, {
    params: {
      remove_cover: removeCover,
      unmatch_metadata: unmatch,
    },
  });
}

async function uploadManuals({
  romId,
  filesToUpload,
}: {
  romId: number;
  filesToUpload: File[];
}): Promise<PromiseSettledResult<unknown>[]> {
  const heartbeat = storeHeartbeat();
  const uploadStore = storeUpload();

  const promises = filesToUpload.map((file) => {
    const formData = new FormData();
    formData.append(file.name, file);

    uploadStore.start(file.name);
    return new Promise((resolve, reject) => {
      api
        .post(`/roms/${romId}/manuals`, formData, {
          headers: {
            "Content-Type": "multipart/form-data",
            "X-Upload-Filename": file.name,
          },
          timeout: heartbeat.value.FRONTEND.UPLOAD_TIMEOUT * 1000,
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

async function removeManual({
  romId,
}: {
  romId: number;
}): Promise<{ data: DetailedRom }> {
  return api.delete(`/roms/${romId}/manuals`);
}

async function updateUserRomProps({
  romId,
  data,
  updateLastPlayed = false,
  removeLastPlayed = false,
}: {
  romId: number;
  data: Partial<RomUserSchema>;
  updateLastPlayed?: boolean;
  removeLastPlayed?: boolean;
}): Promise<{ data: RomUserSchema }> {
  return api.put(`/roms/${romId}/props`, {
    data: data,
    update_last_played: updateLastPlayed,
    remove_last_played: removeLastPlayed,
  });
}

async function deleteRoms({
  roms,
  deleteFromFs = [],
}: {
  roms: SimpleRom[];
  deleteFromFs: number[];
}): Promise<{ data: BulkOperationResponse }> {
  return api.post("/roms/delete", {
    roms: roms.map((r) => r.id),
    delete_from_fs: deleteFromFs,
  });
}

// Multi-note management functions
async function createRomNote({
  romId,
  noteData,
}: {
  romId: number;
  noteData: {
    title: string;
    content?: string;
    is_public?: boolean;
    tags?: string[];
  };
}): Promise<{ data: UserNoteSchema }> {
  return api.post(`/roms/${romId}/notes`, noteData);
}

async function updateRomNote({
  romId,
  noteId,
  noteData,
}: {
  romId: number;
  noteId: number;
  noteData: {
    title?: string;
    content?: string;
    is_public?: boolean;
    tags?: string[];
  };
}): Promise<{ data: UserNoteSchema }> {
  return api.put(`/roms/${romId}/notes/${noteId}`, noteData);
}

async function deleteRomNote({
  romId,
  noteId,
}: {
  romId: number;
  noteId: number;
}): Promise<{ data: UserNoteSchema }> {
  return api.delete(`/roms/${romId}/notes/${noteId}`);
}

async function getRomNotes({
  romId,
  publicOnly = false,
  search,
  tags,
}: {
  romId: number;
  publicOnly?: boolean;
  search?: string;
  tags?: string[];
}): Promise<{ data: UserNoteSchema[] }> {
  return api.get(`/roms/${romId}/notes`, {
    params: {
      public_only: publicOnly,
      search,
      tags: tags?.join(","),
    },
  });
}

export default {
  uploadRoms,
  getRoms,
  getRecentRoms,
  getRecentPlayedRoms,
  getRom,
  getRomByMetadataProvider,
  downloadRom,
  bulkDownloadRoms,
  searchRom,
  updateRom,
  uploadManuals,
  removeManual,
  updateUserRomProps,
  deleteRoms,
  createRomNote,
  updateRomNote,
  deleteRomNote,
  getRomNotes,
};
