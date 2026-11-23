/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type VirtualCollectionSchema = {
    name: string;
    description: string;
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
     * Always true.
     */
    is_virtual?: boolean;
    /**
     * True for a smart collection, whose roms are chosen by its filters.
     */
    is_smart?: boolean;
    created_at: string;
    updated_at: string;
    id: string;
    /**
     * The kind of virtual collection: `genre`, `franchise`, `collection`, `mode`, `company`, `publisher` or `developer`.
     */
    type: string;
    /**
     * The number of roms in the collection.
     */
    readonly rom_count: number;
};

