import api from "@/services/api";
import type {
  Collection,
  VirtualCollection,
  SmartCollection,
} from "@/stores/collections";

export type UpdatedCollection = Collection & {
  artwork?: File;
  url_cover?: string | null;
};

export const collectionApi = api;

async function createCollection({
  collection,
}: {
  collection: Partial<UpdatedCollection>;
}): Promise<{ data: Collection }> {
  const formData = new FormData();
  formData.append("name", collection.name || "");
  formData.append("description", collection.description || "");
  formData.append("url_cover", collection.url_cover || "");
  formData.append("rom_ids", JSON.stringify(collection.rom_ids || []));
  if (collection.artwork) formData.append("artwork", collection.artwork);

  return api.post(`/collections`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: {
      is_public: collection.is_public || false,
      is_favorite: collection.is_favorite || false,
    },
  });
}

async function createSmartCollection({
  smartCollection,
}: {
  smartCollection: Partial<SmartCollection>;
}): Promise<{ data: SmartCollection }> {
  const formData = new FormData();

  formData.append("name", smartCollection.name || "");
  formData.append("description", smartCollection.description || "");
  formData.append(
    "filter_criteria",
    JSON.stringify(smartCollection.filter_criteria),
  );

  return api.post("/collections/smart", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: {
      is_public: smartCollection.is_public,
    },
  });
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

async function getSmartCollections(): Promise<{ data: SmartCollection[] }> {
  return api.get("/collections/smart");
}

async function getCollection(id: number): Promise<{ data: Collection }> {
  return api.get(`/collections/${id}`);
}

async function getVirtualCollection(
  id: string,
): Promise<{ data: VirtualCollection }> {
  return api.get(`/collections/virtual/${id}`);
}

async function getSmartCollection(
  id: number,
): Promise<{ data: SmartCollection }> {
  return api.get(`/collections/smart/${id}`);
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
  formData.append("rom_ids", JSON.stringify(collection.rom_ids || []));
  if (collection.artwork) formData.append("artwork", collection.artwork);

  return api.put(`/collections/${collection.id}`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: { is_public: collection.is_public, remove_cover: removeCover },
  });
}

async function updateSmartCollection({
  smartCollection,
}: {
  smartCollection: SmartCollection;
}): Promise<{ data: SmartCollection }> {
  const formData = new FormData();

  formData.append("name", smartCollection.name || "");
  formData.append("description", smartCollection.description || "");
  formData.append(
    "filter_criteria",
    JSON.stringify(smartCollection.filter_criteria),
  );

  return api.put(`/collections/smart/${smartCollection.id}`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: {
      is_public: smartCollection.is_public,
    },
  });
}

async function deleteCollection({ collection }: { collection: Collection }) {
  return api.delete(`/collections/${collection.id}`);
}

async function deleteSmartCollection(id: number) {
  return api.delete(`/collections/smart/${id}`);
}

export default {
  createCollection,
  createSmartCollection,
  getCollections,
  getVirtualCollections,
  getCollection,
  getVirtualCollection,
  updateCollection,
  deleteCollection,
  getSmartCollections,
  getSmartCollection,
  updateSmartCollection,
  deleteSmartCollection,
};
