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
    /**
     * Offer every current server save the client did not list as a download, even one this device already synced. For clients that never delete saves themselves (such as a browser, whose storage can be evicted), so a missing save means lost rather than deleted.
     */
    restore_unlisted?: boolean;
    /**
     * Emulators whose saves this client can load. When provided, only server saves written by one of them are paired or offered, so a save from another emulator in the same slot is left alone.
     */
    emulators?: (Array<string> | null);
};

