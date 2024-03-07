/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { MetadataSourcesDict } from './MetadataSourcesDict';
import type { SchedulerDict } from './SchedulerDict';
import type { WatcherDict } from './WatcherDict';

export type HeartbeatResponse = {
    VERSION: string;
    NEW_VERSION: string;
    WATCHER: WatcherDict;
    SCHEDULER: SchedulerDict;
    METADATA_SOURCES: MetadataSourcesDict;
};

