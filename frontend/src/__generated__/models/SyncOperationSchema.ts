/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SyncOperationSchema = {
    action: 'upload' | 'download' | 'conflict' | 'no_op';
    rom_id: number;
    save_id?: (number | null);
    file_name: string;
    slot?: (string | null);
    emulator?: (string | null);
    reason: string;
    server_updated_at?: (string | null);
    server_content_hash?: (string | null);
};

