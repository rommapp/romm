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

async function updateCollection({
  collection,
}: {
  collection: Collection;
}): Promise<{ data: MessageResponse }> {
  return api.delete(`/collections/${collection.id}`);
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
