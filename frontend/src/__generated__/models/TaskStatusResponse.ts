/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobStatus } from './JobStatus';
export type TaskStatusResponse = {
    task_name: string;
    task_id: string;
    status: (JobStatus | null);
    queued_at: string;
    started_at: (string | null);
    ended_at: (string | null);
};

