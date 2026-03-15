/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SyncSessionSchema = {
    id: number;
    device_id: string;
    user_id: number;
    status: string;
    initiated_at: string;
    completed_at?: (string | null);
    operations_planned: number;
    operations_completed: number;
    operations_failed: number;
    error_message?: (string | null);
    created_at: string;
    updated_at: string;
};

