import type {
  MemoryCardCreatePayload,
  MemoryCardSchema,
  MemoryCardVersionSchema,
  UserMemoryCardSchema,
} from "@/__generated__";
import api from "@/services/api";

export const memoryCardApi = api;

// A user's own cards, newest-synced first, optionally scoped to one emulator.
async function getMemoryCards({ emulator }: { emulator?: string } = {}) {
  return api.get<MemoryCardSchema[]>("/memory-cards", {
    params: { emulator },
  });
}

// Cards visible to the caller for an emulator: their own plus other users'
// public ones, each enriched with the owner's username.
async function getSharedMemoryCards({ emulator }: { emulator: string }) {
  return api.get<UserMemoryCardSchema[]>("/memory-cards/shared", {
    params: { emulator },
  });
}

// A card's snapshot history, newest first.
async function getMemoryCardVersions({ id }: { id: number }) {
  return api.get<MemoryCardVersionSchema[]>(`/memory-cards/${id}/versions`);
}

async function createMemoryCard(payload: MemoryCardCreatePayload) {
  return api.post<MemoryCardSchema>("/memory-cards", payload);
}

async function renameMemoryCard({ id, name }: { id: number; name: string }) {
  return api.put<MemoryCardSchema>(`/memory-cards/${id}`, { name });
}

async function setMemoryCardVisibility({
  id,
  isPublic,
}: {
  id: number;
  isPublic: boolean;
}) {
  return api.put<MemoryCardSchema>(`/memory-cards/${id}/visibility`, {
    is_public: isPublic,
  });
}

async function deleteMemoryCards({ cards }: { cards: MemoryCardSchema[] }) {
  return api.post<number[]>("/memory-cards/delete", {
    cards: cards.map((c) => c.id),
  });
}

export default {
  getMemoryCards,
  getSharedMemoryCards,
  getMemoryCardVersions,
  createMemoryCard,
  renameMemoryCard,
  setMemoryCardVisibility,
  deleteMemoryCards,
};
