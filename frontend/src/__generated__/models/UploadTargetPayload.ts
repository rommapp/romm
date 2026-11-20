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
     * A subfolder of the ROM's folder, as a relative path with forward slashes. Empty for the ROM's folder itself.
     */
    folder?: string;
    /**
     * The file name. Overrides the `x-upload-filename` header, which can only hold Latin-1 characters.
     */
    filename?: (string | null);
    /**
     * Replace a file of the same name in the ROM's folder instead of refusing the upload.
     */
    overwrite?: boolean;
};

