/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RomFileSchema } from './RomFileSchema';
import type { RomFlashpointMetadata } from './RomFlashpointMetadata';
import type { RomGamelistMetadata } from './RomGamelistMetadata';
import type { RomHasheousMetadata } from './RomHasheousMetadata';
import type { RomHLTBMetadata } from './RomHLTBMetadata';
import type { RomIGDBMetadata } from './RomIGDBMetadata';
import type { RomLaunchboxMetadata } from './RomLaunchboxMetadata';
import type { RomMetadataSchema } from './RomMetadataSchema';
import type { RomMobyMetadata } from './RomMobyMetadata';
import type { RomRAMetadata } from './RomRAMetadata';
import type { RomSSMetadata } from './RomSSMetadata';
import type { RomUserSchema } from './RomUserSchema';
import type { SaveSchema } from './SaveSchema';
import type { ScreenshotSchema } from './ScreenshotSchema';
import type { SiblingRomSchema } from './SiblingRomSchema';
import type { StateSchema } from './StateSchema';
import type { UserCollectionSchema } from './UserCollectionSchema';
import type { UserNoteSchema } from './UserNoteSchema';
export type DetailedRomSchema = {
    id: number;
    igdb_id: (number | null);
    sgdb_id: (number | null);
    moby_id: (number | null);
    ss_id: (number | null);
    ra_id: (number | null);
    launchbox_id: (number | null);
    hasheous_id: (number | null);
    tgdb_id: (number | null);
    flashpoint_id: (string | null);
    hltb_id: (number | null);
    gamelist_id: (string | null);
    platform_id: number;
    platform_slug: string;
    platform_fs_slug: string;
    platform_custom_name: (string | null);
    platform_display_name: string;
    fs_name: string;
    fs_name_no_tags: string;
    fs_name_no_ext: string;
    fs_extension: string;
    fs_path: string;
    fs_size_bytes: number;
    name: (string | null);
    slug: (string | null);
    summary: (string | null);
    alternative_names: Array<string>;
    youtube_video_id: (string | null);
    metadatum: RomMetadataSchema;
    igdb_metadata: (RomIGDBMetadata | null);
    moby_metadata: (RomMobyMetadata | null);
    ss_metadata: (RomSSMetadata | null);
    launchbox_metadata: (RomLaunchboxMetadata | null);
    hasheous_metadata: (RomHasheousMetadata | null);
    flashpoint_metadata: (RomFlashpointMetadata | null);
    hltb_metadata: (RomHLTBMetadata | null);
    gamelist_metadata: (RomGamelistMetadata | null);
    path_cover_small: (string | null);
    path_cover_large: (string | null);
    url_cover: (string | null);
    has_manual: boolean;
    path_manual: (string | null);
    url_manual: (string | null);
    is_identifying?: boolean;
    is_unidentified: boolean;
    is_identified: boolean;
    revision: (string | null);
    regions: Array<string>;
    languages: Array<string>;
    tags: Array<string>;
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    /**
     * @deprecated
     */
    multi: boolean;
    has_simple_single_file: boolean;
    has_nested_single_file: boolean;
    has_multiple_files: boolean;
    files: Array<RomFileSchema>;
    full_path: string;
    created_at: string;
    updated_at: string;
    missing_from_fs: boolean;
    siblings: Array<SiblingRomSchema>;
    rom_user: RomUserSchema;
    merged_ra_metadata: (RomRAMetadata | null);
    merged_screenshots: Array<string>;
    user_saves: Array<SaveSchema>;
    user_states: Array<StateSchema>;
    user_screenshots: Array<ScreenshotSchema>;
    user_collections: Array<UserCollectionSchema>;
    all_user_notes: Array<UserNoteSchema>;
};

