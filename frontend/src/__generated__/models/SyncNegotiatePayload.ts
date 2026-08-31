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
    /**
     * IDs of the ROMs installed on the device. When provided, downloads are offered only for these ROMs (plus any ROM the client sent a save for) instead of the user's whole save library. This is a read-only scope: omitting a ROM never deletes or unlinks its saves. At most 500 IDs per request.
     */
    rom_ids?: (Array<number> | null);
};

