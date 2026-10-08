/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ConflictReason } from './ConflictReason';
import type { CurrentRefSchema } from './CurrentRefSchema';
import type { SnapshotSchema } from './SnapshotSchema';
export type SnapshotConflictSchema = {
    current: (CurrentRefSchema | null);
    branch: SnapshotSchema;
    /**
     * `moved`: the channel moved on from the current the push built on. `moved_from_older`: the push built on a snapshot older than the current it expected, and the channel moved on from that current too.
     */
    reason: ConflictReason;
};

