/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocMetaSchema } from './DocMetaSchema';
import type { RomArchiveMember } from './RomArchiveMember';
import type { RomFileCategory } from './RomFileCategory';
import type { TrackMetaSchema } from './TrackMetaSchema';
export type RomFileSchema = {
    /**
     * The internal ID of the file.
     */
    id: number;
    /**
     * The internal ID of the rom.
     */
    rom_id: number;
    /**
     * The file name, extension included.
     */
    file_name: string;
    /**
     * The folder holding the file.
     */
    file_path: string;
    /**
     * The size of the file, in bytes.
     */
    file_size_bytes: number;
    /**
     * The path to the file on disk.
     */
    full_path: string;
    /**
     * True when the file sits at the top level of the rom.
     */
    is_top_level: boolean;
    /**
     * When the record was created.
     */
    created_at: string;
    /**
     * When the record last changed.
     */
    updated_at: string;
    /**
     * When the file was last modified on disk.
     */
    last_modified: (string | null);
    /**
     * The CRC32 hash of the file.
     */
    crc_hash: (string | null);
    /**
     * The MD5 hash of the file.
     */
    md5_hash: (string | null);
    /**
     * The SHA-1 hash of the file.
     */
    sha1_hash: (string | null);
    /**
     * The hash RetroAchievements matches the file on.
     */
    ra_hash: (string | null);
    /**
     * The CHD SHA-1 hash, for a CHD file.
     */
    chd_sha1_hash: (string | null);
    /**
     * The members of the archive, when the file is an archive.
     */
    archive_members: (Array<RomArchiveMember> | null);
    /**
     * The category of the file, such as a manual or a soundtrack.
     */
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

