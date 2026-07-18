/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeviceSyncSchema } from './DeviceSyncSchema';
import type { ScreenshotSchema } from './ScreenshotSchema';
/**
 * A save enriched with its owner's username, for the community (My /
 * Community) view. Mirrors UserScreenshotSchema.
 */
export type UserSaveSchema = {
    id: number;
    rom_id: number;
    user_id: number;
    file_name: string;
    file_name_no_tags: string;
    file_name_no_ext: string;
    file_extension: string;
    file_path: string;
    file_size_bytes: number;
    full_path: string;
    download_path: string;
    missing_from_fs: boolean;
    created_at: string;
    updated_at: string;
    emulator: (string | null);
    slot?: (string | null);
    content_hash?: (string | null);
    is_public?: boolean;
    screenshot: (ScreenshotSchema | null);
    origin_device_id?: (string | null);
    device_syncs?: Array<DeviceSyncSchema>;
    username: string;
    user_avatar_path?: string;
    user_updated_at?: (string | null);
};

