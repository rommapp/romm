/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Why a session the caller held is gone, left behind for their next poll.
 *
 * Only an admin force-release records one; a session the player released or
 * that simply expired leaves no notice.
 */
export type SessionTerminationSchema = {
    ended_by?: (string | null);
    reason?: (string | null);
    ended_at?: (string | null);
    platform?: (string | null);
    rom_id?: (number | null);
    rom_name?: (string | null);
};

