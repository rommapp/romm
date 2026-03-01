import type {
  Body_add_collection_api_collections_post as AddCollectionInput,
  Body_add_smart_collection_api_collections_smart_post as AddSmartCollectionInput,
  Body_update_collection_api_collections__id__put as UpdateCollectionInput,
  Body_update_smart_collection_api_collections_smart__id__put as UpdateSmartCollectionInput,
  CollectionSchema,
  SmartCollectionSchema,
  VirtualCollectionSchema,
} from "@/__generated__";
import api from "@/services/api";
import { buildFormInput } from "@/utils/formData";

type Collection = CollectionSchema;
type VirtualCollection = VirtualCollectionSchema;
type SmartCollection = SmartCollectionSchema;

export type UpdatedCollection = Collection & {
  artwork?: File;
  url_cover?: string | null;
};

export const collectionApi = api;

async function createCollection({
  collection,
}: {
  collection: Partial<UpdatedCollection>;
}) {
  const formData = buildFormInput<AddCollectionInput>([
    ["name", collection.name],
    ["description", collection.description],
    ["url_cover", collection.url_cover],
    ["artwork", collection.artwork],
  ]);

  const { data } = await api.post<Collection>(`/collections`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    params: {
      is_public: collection.is_public || false,
      is_favorite: collection.is_favorite || false,
    },
  });
  return data;
}

async function createSmartCollection({
  smartCollection,
}: {
  smartCollection: Partial<SmartCollection>;
}) {
  const formData = buildFormInput<AddSmartCollectionInput>([
    ["name", smartCollection.name],
    ["description", smartCollection.description],
    [
      "filter_criteria",
      JSON.stringify(smartCollection.filter_criteria) || "{}",
    ],
  ]);

  const { data } = await api.post<SmartCollection>(
    "/collections/smart",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      params: {
        is_public: smartCollection.is_public,
      },
    },
  );
  return data;
}

async function getCollections() {
  return api.get<Collection[]>("/collections");
}

async function getVirtualCollections({
  type = "collection",
}: {
  type?: string;
  limit?: number;
}) {
  return api.get<VirtualCollection[]>("/collections/virtual", {
    params: { type },
  });
}

async function getSmartCollections() {
  return api.get<SmartCollection[]>("/collections/smart");
}

async function getCollection(id: number) {
  return api.get<Collection>(`/collections/${id}`);
}

async function getVirtualCollection(id: string) {
  return api.get<VirtualCollection>(`/collections/virtual/${id}`);
}

async function getSmartCollection(id: number) {
  return api.get<SmartCollection>(`/collections/smart/${id}`);
}

async function updateCollection({
  collection,
  removeCover = false,
}: {
  collection: UpdatedCollection;
  removeCover?: boolean;
}) {
  const formData = buildFormInput<UpdateCollectionInput>([
    ["name", collection.name],
    ["description", collection.description],
    ["url_cover", collection.url_cover],
    ["rom_ids", JSON.stringify(collection.rom_ids)],
    ["artwork", collection.artwork],
  ]);

  return api.put<Collection>(`/collections/${collection.id}`, formData, {
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
}) {
  const formData = buildFormInput<UpdateSmartCollectionInput>([
    ["name", smartCollection.name],
    ["description", smartCollection.description],
    [
      "filter_criteria",
      JSON.stringify(smartCollection.filter_criteria) || "{}",
    ],
  ]);

  return api.put<SmartCollection>(
    `/collections/smart/${smartCollection.id}`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      params: {
        is_public: smartCollection.is_public,
      },
    },
  );
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
