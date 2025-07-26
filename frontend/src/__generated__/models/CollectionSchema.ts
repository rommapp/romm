/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CollectionSchema = {
    name: string;
    description: string;
    rom_ids: Array<number>;
    rom_count: number;
    path_cover_small: (string | null);
    path_cover_large: (string | null);
    path_covers_small: Array<string>;
    path_covers_large: Array<string>;
    is_public?: boolean;
    is_favorite?: boolean;
    is_virtual?: boolean;
    is_smart?: boolean;
    created_at: string;
    updated_at: string;
    id: number;
    url_cover: (string | null);
    user_id: number;
    user__username: string;
};

