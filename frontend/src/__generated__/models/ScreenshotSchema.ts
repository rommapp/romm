/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ScreenshotSchema = {
    id: number;
    rom_id: number;
    user_id: number;
    /**
     * The file name, extension included.
     */
    file_name: string;
    /**
     * The file name without its extension or any tags in parentheses or brackets.
     */
    file_name_no_tags: string;
    file_name_no_ext: string;
    file_extension: string;
    /**
     * The folder holding the file.
     */
    file_path: string;
    file_size_bytes: number;
    full_path: string;
    download_path: string;
    missing_from_fs: boolean;
    created_at: string;
    updated_at: string;
    /**
     * True for a screenshot shown in the gallery, and false for a thumbnail captured with a save or state.
     */
    is_gallery?: boolean;
    is_public?: boolean;
};

