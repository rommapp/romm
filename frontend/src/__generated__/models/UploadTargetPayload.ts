/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Optional body of `/start`: upload into a ROM's folder instead of the
 * platform folder, and name the file where the header cannot.
 */
export type UploadTargetPayload = {
    /**
     * Upload into this ROM's folder instead of the platform folder.
     */
    rom_id?: (number | null);
    /**
     * Subfolder inside the ROM's folder, relative and forward-slashed. Empty for the root.
     */
    folder?: string;
    /**
     * The file name. Takes precedence over the header, which cannot carry characters outside Latin-1.
     */
    filename?: (string | null);
    /**
     * Replace a file of the same name in the ROM's folder instead of refusing the upload.
     */
    overwrite?: boolean;
};

