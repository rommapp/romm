import type { CollectionSchema } from "@/__generated__";

const WRITTEN_AT = "2026-09-16T12:00:00Z";

export function collectionFixture(
  overrides: Partial<CollectionSchema> = {},
): CollectionSchema {
  return {
    id: 1,
    name: "Favorites",
    description: "",
    rom_ids: [],
    rom_count: 0,
    path_cover_small: null,
    path_cover_large: null,
    path_covers_small: [],
    path_covers_large: [],
    is_public: false,
    is_favorite: false,
    created_at: WRITTEN_AT,
    updated_at: WRITTEN_AT,
    url_cover: null,
    user_id: 1,
    owner_username: "admin",
    ...overrides,
  };
}
