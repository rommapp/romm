/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncMode } from './SyncMode';
export type DeviceCreatePayload = {
    name?: (string | null);
    platform?: (string | null);
    client?: (string | null);
    client_version?: (string | null);
    ip_address?: (string | null);
    mac_address?: (string | null);
    hostname?: (string | null);
    sync_mode?: (SyncMode | null);
    sync_config?: (Record<string, any> | null);
    allow_existing?: boolean;
    allow_duplicate?: boolean;
    reset_syncs?: boolean;
};

