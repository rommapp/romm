/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocMetaSchema } from './DocMetaSchema';
import type { RomArchiveMember } from './RomArchiveMember';
import type { RomFileCategory } from './RomFileCategory';
import type { TrackMetaSchema } from './TrackMetaSchema';
export type RomFileSchema = {
    id: number;
    rom_id: number;
    /**
     * The file name, extension included.
     */
    file_name: string;
    /**
     * The folder holding the file.
     */
    file_path: string;
    file_size_bytes: number;
    full_path: string;
    is_top_level: boolean;
    /**
     * True when the file is gone from disk.
     */
    missing_from_fs: boolean;
    created_at: string;
    updated_at: string;
    /**
     * When the file was last modified on disk.
     */
    last_modified: (string | null);
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    /**
     * The hash RetroAchievements uses to identify the file.
     */
    ra_hash: (string | null);
    chd_sha1_hash: (string | null);
    archive_members: (Array<RomArchiveMember> | null);
    category: (RomFileCategory | null);
    /**
     * The audio tags of a soundtrack file.
     */
    track_meta?: (TrackMetaSchema | null);
    /**
     * The details of a manual or walkthrough file.
     */
    doc_meta?: (DocMetaSchema | null);
};

