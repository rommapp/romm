/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type UploadStartPayload = {
    platform_id: number;
    filename: string;
    total_size: number;
    total_chunks: number;
    /**
     * Upload into this ROM's folder instead of the platform folder.
     */
    rom_id?: (number | null);
    /**
     * Subfolder inside the ROM's folder, relative and forward-slashed. Empty for the root.
     */
    folder?: string;
};

