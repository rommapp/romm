/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PatchRequest = {
    /**
     * ID of the patch file (RomFile) to apply.
     */
    patch_file_id: number;
    /**
     * Custom output file name. If omitted, derived from ROM + patch names.
     */
    output_file_name?: (string | null);
};

