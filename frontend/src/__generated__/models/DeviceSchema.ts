/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncMode } from './SyncMode';
export type DeviceSchema = {
    id: string;
    user_id: number;
    name: (string | null);
    platform: (string | null);
    client: (string | null);
    client_version: (string | null);
    ip_address: (string | null);
    mac_address: (string | null);
    hostname: (string | null);
    sync_mode: SyncMode;
    sync_enabled: boolean;
    last_seen: (string | null);
    created_at: string;
    updated_at: string;
};

