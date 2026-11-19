/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TaskType } from './TaskType';
export type TaskInfo = {
    /**
     * The name of the task.
     */
    name: string;
    type: TaskType;
    /**
     * Whether the task can be run manually.
     */
    manual_run: boolean;
    /**
     * The display title of the task.
     */
    title: string;
    /**
     * What the task does.
     */
    description: string;
    /**
     * Whether the task is enabled.
     */
    enabled: boolean;
    /**
     * Whether the task is marked destructive.
     */
    destructive: boolean;
    /**
     * The cron schedule of the task. Empty when it has none.
     */
    cron_string: string;
};

