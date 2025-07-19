/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_delete_roms_api_roms_delete_post = {
    /**
     * List of rom ids to delete from database.
     */
    roms: Array<number>;
    /**
     * List of rom ids to delete from filesystem.
     */
    delete_from_fs?: Array<number>;
};

