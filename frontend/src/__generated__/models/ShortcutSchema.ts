/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LaunchMode } from './LaunchMode';
import type { ShortcutStatus } from './ShortcutStatus';
export type ShortcutSchema = {
    id: number;
    user_id: number;
    device_id: string;
    rom_id: number;
    status: ShortcutStatus;
    launch_mode: (LaunchMode | null);
    steam_app_id: (number | null);
    external_id: (string | null);
    error: (string | null);
    created_at: string;
    updated_at: string;
};

