/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SchedulerDict } from './SchedulerDict';
import type { WatcherDict } from './WatcherDict';

export type HeartbeatResponse = {
    VERSION: string;
    NEW_VERSION: string;
    ROMM_AUTH_ENABLED: boolean;
    WATCHER: WatcherDict;
    SCHEDULER: SchedulerDict;
};

