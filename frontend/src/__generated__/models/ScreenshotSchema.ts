/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ScreenshotSchema = {
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
     * True for a screenshot shown in the gallery. Thumbnails captured with saves and states are not.
     */
    is_gallery?: boolean;
    /**
     * Whether other users can see the screenshot.
     */
    is_public?: boolean;
};

