/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CollectionSchema = {
    id: number;
    name: string;
    description: string;
    path_cover_small: (string | null);
    path_cover_large: (string | null);
    url_cover: string;
    roms: Array<number>;
    rom_count: number;
    user_id: number;
    user__username: string;
    is_public: boolean;
    is_favorite: boolean;
    created_at: string;
    updated_at: string;
};

