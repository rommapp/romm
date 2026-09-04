/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Optional body of `/start`: upload into a ROM's folder instead of the
 * platform folder.
 */
export type UploadTargetPayload = {
    rom_id: number;
    /**
     * Subfolder inside the ROM's folder, relative and forward-slashed. Empty for the root.
     */
    folder?: string;
};

