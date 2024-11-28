/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { EmulationDict } from './EmulationDict';
import type { FrontendDict } from './FrontendDict';
import type { MetadataSourcesDict } from './MetadataSourcesDict';
import type { OIDCDict } from './OIDCDict';
import type { SchedulerDict } from './SchedulerDict';
import type { WatcherDict } from './WatcherDict';

export type HeartbeatResponse = {
    VERSION: string;
    SHOW_SETUP_WIZARD: boolean;
    WATCHER: WatcherDict;
    SCHEDULER: SchedulerDict;
    ANY_SOURCE_ENABLED: boolean;
    METADATA_SOURCES: MetadataSourcesDict;
    FS_PLATFORMS: Array<any>;
    EMULATION: EmulationDict;
    FRONTEND: FrontendDict;
    OIDC: OIDCDict;
};

