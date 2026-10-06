/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CurrentRefSchema } from './CurrentRefSchema';
import type { SnapshotSchema } from './SnapshotSchema';
export type SnapshotConflictSchema = {
    current: (CurrentRefSchema | null);
    branch: SnapshotSchema;
};

