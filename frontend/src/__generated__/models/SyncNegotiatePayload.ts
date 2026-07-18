/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClientSaveState } from './ClientSaveState';
export type SyncNegotiatePayload = {
    /**
     * ID of the syncing device. Optional when the request uses a device-bound client token, in which case the device is inferred from the token.
     */
    device_id?: (string | null);
    /**
     * Current save state on the client.
     */
    saves: Array<ClientSaveState>;
};

