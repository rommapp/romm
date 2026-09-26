/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * `streaming:launch-ready`, pushed once the game is up.
 */
export type LaunchReadyPayload = {
    platform: string;
    container: string;
    claimed_at: string;
    host: string;
    resume?: (boolean | null);
};

