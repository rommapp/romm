/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PlaySessionSchema = {
    id: number;
    user_id: number;
    device_id: (string | null);
    rom_id: (number | null);
    sync_session_id: (number | null);
    save_slot: (string | null);
    start_time: string;
    end_time: string;
    duration_ms: number;
    created_at: string;
    updated_at: string;
};

