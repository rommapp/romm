/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A card enriched with its owner's username, for the shared/community
 * picker. Mirrors UserStateSchema.
 */
export type UserMemoryCardSchema = {
    id: number;
    user_id: number;
    emulator: string;
    platform_id?: (number | null);
    name: string;
    slot: number;
    is_public?: boolean;
    created_at: string;
    updated_at: string;
    username: string;
    user_avatar_path?: string;
    user_updated_at?: (string | null);
};

