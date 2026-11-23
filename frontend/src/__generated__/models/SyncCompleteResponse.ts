/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PlaySessionIngestResponse } from './PlaySessionIngestResponse';
import type { SyncSessionSchema } from './SyncSessionSchema';
export type SyncCompleteResponse = {
    session: SyncSessionSchema;
    play_session_ingest?: (PlaySessionIngestResponse | null);
};

