/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PS3ConsoleCreatePayload = {
    ftp_port?: number;
    /**
     * The PS3 user profile whose saves are synced.
     */
    ps3_user?: string;
    poll_interval_minutes?: number;
    keep_versions?: number;
    name: string;
    ip_address: string;
};

