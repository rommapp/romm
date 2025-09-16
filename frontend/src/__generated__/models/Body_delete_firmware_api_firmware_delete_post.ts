/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_delete_firmware_api_firmware_delete_post = {
    /**
     * List of firmware ids to delete from database.
     */
    firmware: Array<number>;
    /**
     * List of firmware ids to delete from filesystem.
     */
    delete_from_fs?: Array<number>;
};

