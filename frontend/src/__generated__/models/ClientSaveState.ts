/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ClientSaveState = {
    /**
     * ID of the ROM this save belongs to.
     */
    rom_id: number;
    /**
     * Name of the save file on the client.
     */
    file_name: string;
    /**
     * The save slot name. Client and server saves pair on (rom_id, slot), so a stable name such as `autosave` keeps a save in sync across negotiations. A null slot marks an archival, manual-upload save that never pairs with a slotted server save, so it always negotiates as an `upload`, even when the server holds an identical file in a slot.
     */
    slot?: (string | null);
    /**
     * Emulator that produced the save, if known.
     */
    emulator?: (string | null);
    /**
     * Hash of the save contents, used to detect identical saves.
     */
    content_hash?: (string | null);
    /**
     * Last-modified timestamp of the save on the client.
     */
    updated_at: string;
    /**
     * Size of the save file in bytes.
     */
    file_size_bytes: number;
};

