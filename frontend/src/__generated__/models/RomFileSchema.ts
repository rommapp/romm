/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RomFileCategory } from './RomFileCategory';
export type RomFileSchema = {
    id: number;
    rom_id: number;
    file_name: string;
    file_path: string;
    file_size_bytes: number;
    full_path: string;
    created_at: string;
    updated_at: string;
    last_modified: string;
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    category: (RomFileCategory | null);
};

