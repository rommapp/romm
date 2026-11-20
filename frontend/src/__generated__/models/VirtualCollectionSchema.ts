/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type VirtualCollectionSchema = {
    /**
     * The name of the collection.
     */
    name: string;
    /**
     * The description of the collection.
     */
    description: string;
    /**
     * The IDs of the roms in the collection. Roms hidden from the caller are left out.
     */
    rom_ids: Array<number>;
    /**
     * The path to the small cover image.
     */
    path_cover_small: (string | null);
    /**
     * The path to the large cover image.
     */
    path_cover_large: (string | null);
    /**
     * The paths to the small covers shown for the collection.
     */
    path_covers_small: Array<string>;
    /**
     * The paths to the large covers shown for the collection.
     */
    path_covers_large: Array<string>;
    /**
     * Whether other users can see the collection.
     */
    is_public?: boolean;
    /**
     * Whether the collection is marked as a favorite.
     */
    is_favorite?: boolean;
    /**
     * Always true.
     */
    is_virtual?: boolean;
    /**
     * True for a smart collection, which its filters define.
     */
    is_smart?: boolean;
    /**
     * When the collection was created.
     */
    created_at: string;
    /**
     * When the collection last changed.
     */
    updated_at: string;
    /**
     * The ID of the virtual collection.
     */
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

