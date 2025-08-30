/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EmulationDict } from './EmulationDict';
import type { FilesystemDict } from './FilesystemDict';
import type { FrontendDict } from './FrontendDict';
import type { MetadataSourcesDict } from './MetadataSourcesDict';
import type { OIDCDict } from './OIDCDict';
import type { SystemDict } from './SystemDict';
import type { TasksDict } from './TasksDict';
export type HeartbeatResponse = {
    SYSTEM: SystemDict;
    METADATA_SOURCES: MetadataSourcesDict;
    FILESYSTEM: FilesystemDict;
    EMULATION: EmulationDict;
    FRONTEND: FrontendDict;
    OIDC: OIDCDict;
    TASKS: TasksDict;
};

