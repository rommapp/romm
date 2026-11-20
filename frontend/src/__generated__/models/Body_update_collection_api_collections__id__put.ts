/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_update_collection_api_collections__id__put = {
    /**
     * Collection artwork file.
     */
    artwork?: (string | null);
    /**
     * Collection ROM IDs as a JSON array string (e.g. [1,2,3]).
     */
    rom_ids: string;
    /**
     * The new name. Leave it out to keep the current name.
     */
    name?: (string | null);
    /**
     * The new description. Leave it out to keep the current description.
     */
    description?: (string | null);
    /**
     * Updated remote cover URL.
     */
    url_cover?: (string | null);
};

