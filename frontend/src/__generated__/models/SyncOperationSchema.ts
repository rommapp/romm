/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SyncOperationSchema = {
    /**
     * Operation the client should perform. 'upload' when the client has a save the server lacks (including any null-slot save, which is never paired with server saves), 'download' when the server has a newer or unknown save, 'conflict' when both sides changed independently, and 'no_op' when no action is needed.
     */
    action: 'upload' | 'download' | 'conflict' | 'no_op';
    /**
     * ID of the ROM this operation applies to.
     */
    rom_id: number;
    /**
     * ID of the server save, if one exists (null for uploads).
     */
    save_id?: (number | null);
    /**
     * Name of the save file.
     */
    file_name: string;
    /**
     * Slot the operation applies to. Echoes the client slot for uploads; for downloads and conflicts it is the server save's slot.
     */
    slot?: (string | null);
    /**
     * Emulator associated with the save, if known.
     */
    emulator?: (string | null);
    /**
     * Human-readable explanation of why this operation was chosen.
     */
    reason: string;
    /**
     * Last-modified timestamp of the server save, when applicable.
     */
    server_updated_at?: (string | null);
    /**
     * Content hash of the server save, when applicable.
     */
    server_content_hash?: (string | null);
};

