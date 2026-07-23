/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RomArchiveMember } from './RomArchiveMember';
import type { RomFileCategory } from './RomFileCategory';
import type { TrackMetaSchema } from './TrackMetaSchema';
export type RomFileSchema = {
    id: number;
    rom_id: number;
    file_name: string;
    file_path: string;
    file_size_bytes: number;
    full_path: string;
    is_top_level: boolean;
    created_at: string;
    updated_at: string;
    last_modified: string;
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    ra_hash: (string | null);
    chd_sha1_hash: (string | null);
    title_id: (string | null);
    save_id: (string | null);
    title_version: (number | null);
    archive_members: (Array<RomArchiveMember> | null);
    category: (RomFileCategory | null);
    track_meta?: (TrackMetaSchema | null);
};

