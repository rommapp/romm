/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MusicTrackRef } from './MusicTrackRef';
export type MusicTrackIdsPayload = {
    tracks?: Array<MusicTrackRef>;
    /**
     * The first song of each file. Use `tracks` instead.
     * @deprecated
     */
    rom_file_ids?: Array<number>;
};

