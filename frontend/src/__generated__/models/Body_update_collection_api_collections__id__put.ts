/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_update_collection_api_collections__id__put = {
    /**
     * Collection artwork file.
     */
    artwork?: (Blob | null);
    /**
     * Collection ROM IDs as a JSON array string (e.g. [1,2,3]).
     */
    rom_ids: string;
    name?: (string | null);
    description?: (string | null);
    /**
     * Updated remote cover URL.
     */
    url_cover?: (string | null);
};

