/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SmbStatusSchema = {
    enabled: boolean;
    controller_online: boolean;
    samba_running: boolean;
    samba_version?: (string | null);
    advertised_host?: (string | null);
    advertised_port: number;
    workgroup: string;
    started_at?: (string | null);
    user_count: number;
};

