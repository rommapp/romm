/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ScreenshotSchema } from './ScreenshotSchema';
/**
 * A state enriched with its owner's username, for the community (My /
 * Community) view. Mirrors UserScreenshotSchema.
 */
export type UserStateSchema = {
    /**
     * The ID of the sync channel the row was pushed into. Null means a backup the user manages.
     */
    channel_id?: (string | null);
    /**
     * Whether the owner marked it as a favorite.
     */
    is_favorite?: boolean;
    /**
     * The owner's free-text labels.
     */
    labels?: Array<string>;
    /**
     * The internal ID.
     */
    id: number;
    /**
     * The internal ID of the rom.
     */
    rom_id: number;
    /**
     * The ID of the user who owns it.
     */
    user_id: number;
    /**
     * The file name, extension included.
     */
    file_name: string;
    /**
     * The file name without its extension or any tags in parentheses or brackets.
     */
    file_name_no_tags: string;
    /**
     * The file name without its extension.
     */
    file_name_no_ext: string;
    /**
     * The file extension.
     */
    file_extension: string;
    /**
     * The folder holding the file.
     */
    file_path: string;
    /**
     * The size of the file, in bytes.
     */
    file_size_bytes: number;
    /**
     * The path to the file on disk.
     */
    full_path: string;
    /**
     * The path to download the file from.
     */
    download_path: string;
    /**
     * True when the file is no longer on disk.
     */
    missing_from_fs: boolean;
    /**
     * When the record was created.
     */
    created_at: string;
    /**
     * When the record last changed.
     */
    updated_at: string;
    /**
     * The emulator that wrote the state.
     */
    emulator: (string | null);
    /**
     * The libretro core that wrote the state.
     */
    core?: (string | null);
    /**
     * Whether other users can see the state.
     */
    is_public?: boolean;
    /**
     * The screenshot stored with the state.
     */
    screenshot: (ScreenshotSchema | null);
    /**
     * The ID of the device the state came from.
     */
    origin_device_id?: (string | null);
    /**
     * The username of the owner.
     */
    username: string;
    /**
     * The path to the owner's avatar.
     */
    user_avatar_path?: string;
    /**
     * When the owner's record last changed.
     */
    user_updated_at?: (string | null);
};

