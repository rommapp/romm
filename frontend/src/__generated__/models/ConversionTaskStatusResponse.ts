/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ConversionTaskMeta } from './ConversionTaskMeta';
import type { JobStatus } from './JobStatus';
export type ConversionTaskStatusResponse = {
    task_name: string;
    task_id: string;
    status: JobStatus;
    created_at: (string | null);
    enqueued_at: (string | null);
    started_at: (string | null);
    ended_at: (string | null);
    task_type: string;
    meta: ConversionTaskMeta;
};

