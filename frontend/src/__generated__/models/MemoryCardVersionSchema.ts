/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A single snapshot in a card's history. Unlike the ROM-scoped assets it
 * has no rom_id/user_id, so it does not reuse the shared BaseAsset schema.
 */
export type MemoryCardVersionSchema = {
    id: number;
    memory_card_id: number;
    file_name: string;
    file_size_bytes: number;
    content_hash?: (string | null);
    download_path: string;
    missing_from_fs: boolean;
    created_at: string;
    updated_at: string;
};

