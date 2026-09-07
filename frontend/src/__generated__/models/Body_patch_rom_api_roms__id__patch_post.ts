/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_patch_rom_api_roms__id__patch_post = {
    /**
     * ID of a library patch file (RomFile) to apply.
     */
    patch_file_id?: (number | null);
    /**
     * Custom output file name. If omitted, derived from ROM + patch names.
     */
    output_file_name?: (string | null);
    /**
     * A patch file uploaded from the client, applied without being stored in the library.
     */
    patch_file?: (string | null);
};

