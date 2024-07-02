import type { MessageResponse } from "@/__generated__";
import api from "@/services/api/index";
import type { Collection } from "@/stores/collections";

export const collectionApi = api;

async function createCollection({
  name,
  description,
}: {
  name: string;
  description: string;
}): Promise<{ data: Collection }> {
  return api.post("/collections", { name: name, description: description });
}

async function getCollections(): Promise<{ data: Collection[] }> {
  return api.get("/collections");
}

async function getCollection(
  id: number | undefined,
): Promise<{ data: Collection }> {
  return api.get(`/collections/${id}`);
}

export type UpdateCollection = Collection & {
  artwork?: File;
  url_cover?: string;
};

async function updateCollection({
  collection,
  removeCover = false,
}: {
  collection: UpdateCollection;
  removeCover?: boolean;
}): Promise<{ data: MessageResponse }> {
  const formData = new FormData();
  formData.append("name", collection.name || "");
  formData.append("description", collection.description || "");
  formData.append("url_cover", collection.url_cover || "");
  if (collection.artwork) formData.append("artwork", collection.artwork);
  return api.put(`/collections/${collection.id}`, formData, {
    params: { remove_cover: removeCover },
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
