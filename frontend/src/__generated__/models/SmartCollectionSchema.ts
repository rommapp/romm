/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SmartCollectionSchema = {
    name: string;
    description?: string;
    /**
     * The IDs of the roms in the collection. Roms hidden from the caller are left out.
     */
    rom_ids: Array<number>;
    path_cover_small: (string | null);
    path_cover_large: (string | null);
    /**
     * The small covers of the roms in the collection, used to build a collage when `path_cover_small` is empty.
     */
    path_covers_small: Array<string>;
    /**
     * The large covers of the roms in the collection, used to build a collage when `path_cover_large` is empty.
     */
    path_covers_large: Array<string>;
    is_public?: boolean;
    is_favorite?: boolean;
    /**
     * True for a virtual collection, which is generated from the library's metadata.
     */
    is_virtual?: boolean;
    /**
     * Always true.
     */
    is_smart?: boolean;
    created_at: string;
    updated_at: string;
    id: number;
    filter_criteria: Record<string, any>;
    filter_summary: string;
    user_id: number;
    owner_username: string;
    /**
     * The number of roms in the collection.
     */
    readonly rom_count: number;
};

