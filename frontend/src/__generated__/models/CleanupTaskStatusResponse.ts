/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CleanupTaskMeta } from './CleanupTaskMeta';
import type { JobStatus } from './JobStatus';
export type CleanupTaskStatusResponse = {
    /**
     * The key of the task in the catalog. Null for scans started outside the catalog, by a client or the watcher.
     */
    task_key: (string | null);
    /**
     * The name of the task.
     */
    task_name: string;
    /**
     * The job ID, which `GET /tasks/{task_id}` takes.
     */
    task_id: string;
    status: JobStatus;
    /**
     * When the job was created.
     */
    created_at: (string | null);
    /**
     * When the job was queued.
     */
    enqueued_at: (string | null);
    /**
     * When the job started running.
     */
    started_at: (string | null);
    /**
     * When the job finished.
     */
    ended_at: (string | null);
    /**
     * The kind of task: `cleanup`.
     */
    task_type: string;
    /**
     * Details specific to this kind of task.
     */
    meta: CleanupTaskMeta;
};

