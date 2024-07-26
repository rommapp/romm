import type { MessageResponse } from "@/__generated__";
import api from "@/services/api/index";
import type { Collection } from "@/stores/collections";

export type UpdatedCollection = Collection & {
  artwork?: File;
  url_cover?: string;
};

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
  formData.append("roms", JSON.stringify(collection.roms));
  if (collection.artwork) formData.append("artwork", collection.artwork);
  return api.post(`/collections`, formData);
}

async function getCollections(): Promise<{ data: Collection[] }> {
  return api.get("/collections");
}

async function getCollection(
  id: number | undefined,
): Promise<{ data: Collection }> {
  return api.get(`/collections/${id}`);
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
  formData.append("roms", JSON.stringify(collection.roms));
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

export default {
  createCollection,
  getCollections,
  getCollection,
  updateCollection,
  deleteCollection,
};
