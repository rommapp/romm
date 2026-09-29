/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocMetaSchema } from './DocMetaSchema';
import type { RomArchiveMember } from './RomArchiveMember';
import type { RomFileCategory } from './RomFileCategory';
import type { RomFileContentType } from './RomFileContentType';
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
    last_modified: (string | null);
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    ra_hash: (string | null);
    chd_sha1_hash: (string | null);
    title_id: (string | null);
    title_version: (number | null);
    title: (string | null);
    serial: (string | null);
    content_type: (RomFileContentType | null);
    display_version: (string | null);
    regions: (Array<string> | null);
    languages: (Array<string> | null);
    publisher: (string | null);
    min_firmware_version: (string | null);
    is_compressed: (boolean | null);
    compression: (string | null);
    file_format: (string | null);
    uncompressed_size_bytes: (number | null);
    archive_members: (Array<RomArchiveMember> | null);
    category: (RomFileCategory | null);
    track_meta?: (TrackMetaSchema | null);
    doc_meta?: (DocMetaSchema | null);
};

