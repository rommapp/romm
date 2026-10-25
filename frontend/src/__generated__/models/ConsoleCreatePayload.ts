/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ConsoleCreatePayload = {
    console: 'ps3' | 'ps4';
    name: string;
    ip_address: string;
    ftp_port?: (number | null);
    /**
     * The console user profile whose saves are synced.
     */
    user_id: string;
    poll_interval_minutes?: (number | null);
    keep_versions?: (number | null);
};

