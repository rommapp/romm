/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EmulationDict } from './EmulationDict';
import type { FilesystemDict } from './FilesystemDict';
import type { FrontendDict } from './FrontendDict';
import type { MetadataSourcesDict } from './MetadataSourcesDict';
import type { OIDCDict } from './OIDCDict';
import type { SchedulerDict } from './SchedulerDict';
import type { SystemDict } from './SystemDict';
import type { WatcherDict } from './WatcherDict';

export type HeartbeatResponse = {
    SYSTEM: SystemDict;
    WATCHER: WatcherDict;
    SCHEDULER: SchedulerDict;
    METADATA_SOURCES: MetadataSourcesDict;
    FILESYSTEM: FilesystemDict;
    EMULATION: EmulationDict;
    FRONTEND: FrontendDict;
    OIDC: OIDCDict;
};

