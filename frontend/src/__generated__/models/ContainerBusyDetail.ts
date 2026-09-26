/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The 409 body when a claim finds its container held.
 */
export type ContainerBusyDetail = {
    message: string;
    draining: boolean;
    rom_name: (string | null);
    claimed_at: (string | null);
};

