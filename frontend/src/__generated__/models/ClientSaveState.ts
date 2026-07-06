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
     * Save slot name. Saves are paired between client and server on (rom_id, slot), so provide a stable slot name (e.g. 'autosave') to keep a save in sync across negotiations. A null slot is treated as an archival, manual-upload save: it is never paired with slotted server saves, so a null-slot client save always negotiates as an 'upload' even when an identical file already exists on the server under a slot.
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

