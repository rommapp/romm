import type { AxiosProgressEvent } from "axios";
import type {
  Body_delete_roms_api_roms_delete_post as DeleteRomsInput,
  Body_update_rom_api_roms__id__put as UpdateRomInput,
  BulkOperationResponse,
  DetailedRomSchema,
  ManualMetadata,
  RomUserUpdatePayload,
  RomUserSchema,
  SearchRomSchema,
  SimpleRomSchema,
  UserNoteSchema,
  RomFiltersDict,
} from "@/__generated__";
import { type CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import api from "@/services/api";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storeUpload from "@/stores/upload";
import { getDownloadPath } from "@/utils";
import { buildFormInput, type FormInputField } from "@/utils/formData";

export const romApi = api;
type DetailedRom = DetailedRomSchema;
type SimpleRom = SimpleRomSchema;
type SearchRom = SearchRomSchema;

const DOWNLOAD_CLEANUP_DELAY = 100;

async function uploadRoms({
  platformId,
  filesToUpload,
}: {
  platformId: number;
  filesToUpload: File[];
}) {
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
  platformIds?: number[] | null;
  collectionId?: number | null;
  virtualCollectionId?: string | null;
  smartCollectionId?: number | null;
  searchTerm?: string | null;
  limit?: number;
  offset?: number;
  orderBy?: string | null;
  orderDir?: string | null;
  filterMatched?: boolean | null;
  filterFavorites?: boolean | null;
  filterDuplicates?: boolean | null;
  filterPlayables?: boolean | null;
  filterRA?: boolean | null;
  filterMissing?: boolean | null;
  filterVerified?: boolean | null;
  groupByMetaId?: boolean;
  // Multi-value filters
  selectedGenres?: string[] | null;
  selectedFranchises?: string[] | null;
  selectedCollections?: string[] | null;
  selectedCompanies?: string[] | null;
  selectedAgeRatings?: string[] | null;
  selectedRegions?: string[] | null;
  selectedLanguages?: string[] | null;
  selectedPlayerCounts?: string[] | null;
  selectedStatuses?: string[] | null;
  // Logic operators for multi-value filters
  genresLogic?: string | null;
  franchisesLogic?: string | null;
  collectionsLogic?: string | null;
  companiesLogic?: string | null;
  ageRatingsLogic?: string | null;
  regionsLogic?: string | null;
  languagesLogic?: string | null;
  statusesLogic?: string | null;
  playerCountsLogic?: string | null;
}

async function getRoms({
  platformIds = null,
  collectionId = null,
  virtualCollectionId = null,
  smartCollectionId = null,
  searchTerm = null,
  limit = 72,
  offset = 0,
  orderBy = "name",
  orderDir = "asc",
  filterMatched = null,
  filterFavorites = null,
  filterDuplicates = null,
  filterPlayables = null,
  filterRA = false,
  filterMissing = false,
  filterVerified = false,
  groupByMetaId = false,
  selectedGenres = null,
  selectedFranchises = null,
  selectedCollections = null,
  selectedCompanies = null,
  selectedAgeRatings = null,
  selectedRegions = null,
  selectedLanguages = null,
  selectedPlayerCounts = null,
  selectedStatuses = null,
  // Logic operators
  genresLogic = null,
  franchisesLogic = null,
  collectionsLogic = null,
  companiesLogic = null,
  ageRatingsLogic = null,
  regionsLogic = null,
  languagesLogic = null,
  statusesLogic = null,
  playerCountsLogic = null,
}: GetRomsParams) {
  const params = {
    platform_ids:
      platformIds && platformIds.length > 0 ? platformIds : undefined,
    collection_id: collectionId,
    virtual_collection_id: virtualCollectionId,
    smart_collection_id: smartCollectionId,
    search_term: searchTerm,
    limit: limit,
    offset: offset,
    order_by: orderBy,
    order_dir: orderDir,
    group_by_meta_id: groupByMetaId,
    genres:
      selectedGenres && selectedGenres.length > 0 ? selectedGenres : undefined,
    franchises:
      selectedFranchises && selectedFranchises.length > 0
        ? selectedFranchises
        : undefined,
    collections:
      selectedCollections && selectedCollections.length > 0
        ? selectedCollections
        : undefined,
    companies:
      selectedCompanies && selectedCompanies.length > 0
        ? selectedCompanies
        : undefined,
    age_ratings:
      selectedAgeRatings && selectedAgeRatings.length > 0
        ? selectedAgeRatings
        : undefined,
    statuses:
      selectedStatuses && selectedStatuses.length > 0
        ? selectedStatuses
        : undefined,
    regions:
      selectedRegions && selectedRegions.length > 0
        ? selectedRegions
        : undefined,
    languages:
      selectedLanguages && selectedLanguages.length > 0
        ? selectedLanguages
        : undefined,
    player_counts:
      selectedPlayerCounts && selectedPlayerCounts.length > 0
        ? selectedPlayerCounts
        : undefined,
    // Logic operators
    genres_logic:
      selectedGenres && selectedGenres.length > 0
        ? genresLogic || "any"
        : undefined,
    franchises_logic:
      selectedFranchises && selectedFranchises.length > 0
        ? franchisesLogic || "any"
        : undefined,
    collections_logic:
      selectedCollections && selectedCollections.length > 0
        ? collectionsLogic || "any"
        : undefined,
    companies_logic:
      selectedCompanies && selectedCompanies.length > 0
        ? companiesLogic || "any"
        : undefined,
    age_ratings_logic:
      selectedAgeRatings && selectedAgeRatings.length > 0
        ? ageRatingsLogic || "any"
        : undefined,
    regions_logic:
      selectedRegions && selectedRegions.length > 0
        ? regionsLogic || "any"
        : undefined,
    languages_logic:
      selectedLanguages && selectedLanguages.length > 0
        ? languagesLogic || "any"
        : undefined,
    statuses_logic:
      selectedStatuses && selectedStatuses.length > 0
        ? statusesLogic || "any"
        : undefined,
    player_counts_logic:
      selectedPlayerCounts && selectedPlayerCounts.length > 0
        ? playerCountsLogic || "any"
        : undefined,
    ...(filterMatched !== null ? { matched: filterMatched } : {}),
    ...(filterFavorites !== null ? { favorite: filterFavorites } : {}),
    ...(filterDuplicates !== null ? { duplicate: filterDuplicates } : {}),
    ...(filterPlayables !== null ? { playable: filterPlayables } : {}),
    ...(filterMissing !== null ? { missing: filterMissing } : {}),
    ...(filterRA !== null ? { has_ra: filterRA } : {}),
    ...(filterVerified !== null ? { verified: filterVerified } : {}),
  };

  return api.get<GetRomsResponse>(`/roms`, {
    params,
  });
}

export const RECENT_ROMS_LIMIT = 15;
export const RECENT_PLAYED_ROMS_LIMIT = 15;

async function getRecentRoms() {
  return api.get<GetRomsResponse>("/roms", {
    params: {
      order_by: "id",
      order_dir: "desc",
      limit: RECENT_ROMS_LIMIT,
      with_char_index: false,
      with_filter_values: false,
    },
  });
}

async function getRecentPlayedRoms() {
  return api.get<GetRomsResponse>("/roms", {
    params: {
      order_by: "last_played",
      order_dir: "desc",
      limit: RECENT_PLAYED_ROMS_LIMIT,
      with_char_index: false,
      with_filter_values: false,
      last_played: true,
    },
  });
}

async function getRom({ romId }: { romId: number }) {
  return api.get<DetailedRom>(`/roms/${romId}`);
}

async function getRomByMetadataProvider({
  field,
  id,
}: {
  field: Partial<keyof DetailedRom>;
  id: number;
}) {
  return api.get<DetailedRom>(`/roms/by-metadata-provider/`, {
    params: { [field]: id },
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
}) {
  return api.get<SearchRom[]>("/search/roms", {
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
  manual_metadata?: ManualMetadata | null;
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
}) {
  const fields: FormInputField<UpdateRomInput>[] = [
    ["name", rom.name],
    ["fs_name", rom.fs_name],
    ["summary", rom.summary],
    ["igdb_id", rom.igdb_id?.toString()],
    ["sgdb_id", rom.sgdb_id?.toString()],
    ["moby_id", rom.moby_id?.toString()],
    ["ss_id", rom.ss_id?.toString()],
    ["launchbox_id", rom.launchbox_id?.toString()],
    ["ra_id", rom.ra_id?.toString()],
    ["flashpoint_id", rom.flashpoint_id?.toString()],
    ["hasheous_id", rom.hasheous_id?.toString()],
    ["tgdb_id", rom.tgdb_id?.toString()],
    ["hltb_id", rom.hltb_id?.toString()],
  ];

  if (rom.manual_metadata) {
    fields.push(["raw_manual_metadata", JSON.stringify(rom.manual_metadata)]);
  }

  if (rom.raw_metadata?.igdb_metadata) {
    fields.push(["raw_igdb_metadata", rom.raw_metadata.igdb_metadata]);
  }
  if (rom.raw_metadata?.moby_metadata) {
    fields.push(["raw_moby_metadata", rom.raw_metadata.moby_metadata]);
  }
  if (rom.raw_metadata?.ss_metadata) {
    fields.push(["raw_ss_metadata", rom.raw_metadata.ss_metadata]);
  }
  if (rom.raw_metadata?.launchbox_metadata) {
    fields.push([
      "raw_launchbox_metadata",
      rom.raw_metadata.launchbox_metadata,
    ]);
  }
  if (rom.raw_metadata?.hasheous_metadata) {
    fields.push(["raw_hasheous_metadata", rom.raw_metadata.hasheous_metadata]);
  }
  if (rom.raw_metadata?.flashpoint_metadata) {
    fields.push([
      "raw_flashpoint_metadata",
      rom.raw_metadata.flashpoint_metadata,
    ]);
  }
  if (rom.raw_metadata?.hltb_metadata) {
    fields.push(["raw_hltb_metadata", rom.raw_metadata.hltb_metadata]);
  }

  // Don't set url_cover on manual artwork upload
  if (rom.artwork) {
    fields.push(["artwork", rom.artwork]);
  } else {
    fields.push(["url_cover", rom.url_cover]);
  }
  const formData = buildFormInput<UpdateRomInput>(fields);

  return api.put<DetailedRom>(`/roms/${rom.id}`, formData, {
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
}) {
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

async function removeManual({ romId }: { romId: number }) {
  return api.delete<DetailedRom>(`/roms/${romId}/manuals`);
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
}) {
  const payload: RomUserUpdatePayload = {
    data: data,
    update_last_played: updateLastPlayed,
    remove_last_played: removeLastPlayed,
  };
  return api.put<RomUserSchema>(`/roms/${romId}/props`, payload);
}

async function deleteRoms({
  roms,
  deleteFromFs = [],
}: {
  roms: SimpleRom[];
  deleteFromFs: number[];
}) {
  const payload: DeleteRomsInput = {
    roms: roms.map((r) => r.id),
    delete_from_fs: deleteFromFs,
  };
  return api.post<BulkOperationResponse>("/roms/delete", payload);
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
}) {
  return api.post<UserNoteSchema>(`/roms/${romId}/notes`, noteData);
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
}) {
  return api.put<UserNoteSchema>(`/roms/${romId}/notes/${noteId}`, noteData);
}

async function deleteRomNote({
  romId,
  noteId,
}: {
  romId: number;
  noteId: number;
}) {
  return api.delete<UserNoteSchema>(`/roms/${romId}/notes/${noteId}`);
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
}) {
  return api.get<UserNoteSchema[]>(`/roms/${romId}/notes`, {
    params: {
      public_only: publicOnly,
      search,
      tags: tags?.join(","),
    },
  });
}

async function getRomFilters() {
  return api.get<RomFiltersDict>("/roms/filters");
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
  getRomFilters,
};
