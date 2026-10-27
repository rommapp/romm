/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SnapshotSchema } from './SnapshotSchema';
/**
 * A channel with its current snapshot, null while the channel is empty.
 */
export type ChannelSchema = {
    id: string;
    label: string;
    is_public: boolean;
    is_hardcore: boolean;
    is_own: boolean;
    owner_username: string;
    current_snapshot_id: (number | null);
    rom_id: (number | null);
    rom_file_id: (number | null);
    created_at: string;
    updated_at: string;
    current: (SnapshotSchema | null);
    snapshot_count: number;
};

