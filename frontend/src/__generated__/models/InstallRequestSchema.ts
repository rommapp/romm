/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InstallStatus } from './InstallStatus';
/**
 * An install request, as served and as stored in Redis while pending or taken.
 */
export type InstallRequestSchema = {
    id: string;
    user_id: number;
    device_id: string;
    rom_id: number;
    file_ids: Array<number>;
    status: InstallStatus;
    reason: (string | null);
    created_at: string;
    updated_at: string;
};

