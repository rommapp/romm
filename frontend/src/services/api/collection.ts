import type { MessageResponse } from "@/__generated__";
import api from "@/services/api/index";
import type { Collection, VirtualCollection } from "@/stores/collections";

export type UpdatedCollection = Collection & {
  artwork?: File;
  url_cover?: string | null;
};

// Smart Collection types
export interface SmartCollectionSchema {
  id: number;
  name: string;
  description: string | null;
  filter_criteria: Record<string, any>;
  filter_summary: string;
  rom_count: number;
  path_cover_small: string | null;
  path_cover_large: string | null;
  url_cover: string | null;
  user_id: number;
  user__username: string;
  is_public: boolean;
  is_smart: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateSmartCollectionParams {
  name: string;
  description?: string;
  filter_criteria: Record<string, any>;
  url_cover?: string;
  is_public?: boolean;
  artwork?: File;
}

export interface UpdateSmartCollectionParams {
  name?: string;
  description?: string;
  filter_criteria?: Record<string, any>;
  url_cover?: string;
  is_public?: boolean;
  remove_cover?: boolean;
  artwork?: File;
}

export const collectionApi = api;

async function createCollection({
  collection,
}: {
  collection: UpdatedCollection;
}): Promise<{ data: Collection }> {
  const formData = new FormData();
  formData.append("name", collection.name || "");
  formData.append("description", collection.description || "");
  formData.append("url_cover", collection.url_cover || "");
  formData.append("rom_ids", JSON.stringify(collection.rom_ids));
  if (collection.artwork) formData.append("artwork", collection.artwork);
  return api.post(`/collections`, formData);
}

async function getCollections(): Promise<{ data: Collection[] }> {
  return api.get("/collections");
}

async function getVirtualCollections({
  type = "collection",
}: {
  type?: string;
  limit?: number;
}): Promise<{ data: VirtualCollection[] }> {
  return api.get("/collections/virtual", { params: { type } });
}

async function getCollection(id: number): Promise<{ data: Collection }> {
  return api.get(`/collections/${id}`);
}

async function getVirtualCollection(
  id: string,
): Promise<{ data: VirtualCollection }> {
  return api.get(`/collections/virtual/${id}`);
}

async function updateCollection({
  collection,
  removeCover = false,
}: {
  collection: UpdatedCollection;
  removeCover?: boolean;
}): Promise<{ data: Collection }> {
  const formData = new FormData();
  formData.append("name", collection.name || "");
  formData.append("description", collection.description || "");
  formData.append("url_cover", collection.url_cover || "");
  formData.append("rom_ids", JSON.stringify(collection.rom_ids));
  if (collection.artwork) formData.append("artwork", collection.artwork);
  return api.put(`/collections/${collection.id}`, formData, {
    params: { is_public: collection.is_public, remove_cover: removeCover },
  });
}

async function deleteCollection({
  collection,
}: {
  collection: Collection;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/collections/${collection.id}`);
}

// Smart Collection functions
async function getSmartCollections(): Promise<{
  data: SmartCollectionSchema[];
}> {
  return api.get("/collections/smart");
}

async function getSmartCollection(
  id: number,
): Promise<{ data: SmartCollectionSchema }> {
  return api.get(`/collections/smart/${id}`);
}

async function getSmartCollectionRoms(
  id: number,
): Promise<{ data: { items: any[]; total: number } }> {
  return api.get(`/collections/smart/${id}/roms`);
}

async function createSmartCollection(
  params: CreateSmartCollectionParams,
): Promise<{ data: SmartCollectionSchema }> {
  const formData = new FormData();

  formData.append("name", params.name);
  if (params.description) formData.append("description", params.description);
  formData.append("filter_criteria", JSON.stringify(params.filter_criteria));
  if (params.url_cover) formData.append("url_cover", params.url_cover);
  formData.append("is_public", String(params.is_public || false));
  if (params.artwork) formData.append("artwork", params.artwork);

  return api.post("/collections/smart", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

async function updateSmartCollection(
  id: number,
  params: UpdateSmartCollectionParams,
): Promise<{ data: SmartCollectionSchema }> {
  const formData = new FormData();

  if (params.name) formData.append("name", params.name);
  if (params.description !== undefined)
    formData.append("description", params.description);
  if (params.filter_criteria)
    formData.append("filter_criteria", JSON.stringify(params.filter_criteria));
  if (params.url_cover !== undefined)
    formData.append("url_cover", params.url_cover);
  if (params.is_public !== undefined)
    formData.append("is_public", String(params.is_public));
  if (params.remove_cover)
    formData.append("remove_cover", String(params.remove_cover));
  if (params.artwork) formData.append("artwork", params.artwork);

  return api.put(`/collections/smart/${id}`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: {
      ...(params.remove_cover !== undefined && {
        remove_cover: params.remove_cover,
      }),
      ...(params.is_public !== undefined && { is_public: params.is_public }),
    },
  });
}

async function deleteSmartCollection(
  id: number,
): Promise<{ data: { msg: string } }> {
  return api.delete(`/collections/smart/${id}`);
}

export default {
  createCollection,
  getCollections,
  getVirtualCollections,
  getCollection,
  getVirtualCollection,
  updateCollection,
  deleteCollection,
  // Smart Collection functions
  getSmartCollections,
  getSmartCollection,
  getSmartCollectionRoms,
  createSmartCollection,
  updateSmartCollection,
  deleteSmartCollection,
};
