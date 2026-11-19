/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeviceRefSchema } from './DeviceRefSchema';
export type HeldBySchema = {
    /**
     * The device that holds the snapshot.
     */
    device: DeviceRefSchema;
    /**
     * When the device last synced to the snapshot.
     */
    synced_at: string;
};

