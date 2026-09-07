/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PhysicalRomCreateForm = {
    /**
     * Platform the game belongs to.
     */
    platform_id: number;
    /**
     * Game name to match metadata against.
     */
    name?: (string | null);
    /**
     * UPC/EAN/barcode of the physical copy.
     */
    upc?: (string | null);
    /**
     * Metadata providers to match against; defaults to all enabled.
     */
    metadata_sources?: (Array<string> | null);
};

