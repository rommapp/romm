/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The 202 a claim answers with: the container is reserved and the game is
 * on its way up. The room URL follows over the socket, since only the
 * broker's launch reply carries it.
 */
export type LaunchingSessionSchema = {
    platform: string;
    container: string;
    label: string;
    rom_name: string;
    claimed_at: string;
};

