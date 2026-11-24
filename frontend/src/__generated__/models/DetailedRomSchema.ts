/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChannelSchema } from './ChannelSchema';
import type { ManualMetadata } from './ManualMetadata';
import type { RomCsdbMetadata } from './RomCsdbMetadata';
import type { RomDemozooMetadata } from './RomDemozooMetadata';
import type { RomFileSchema } from './RomFileSchema';
import type { RomFlashpointMetadata } from './RomFlashpointMetadata';
import type { RomGamelistMetadata } from './RomGamelistMetadata';
import type { RomHasheousMetadata } from './RomHasheousMetadata';
import type { RomHLTBMetadata } from './RomHLTBMetadata';
import type { RomIGDBMetadata } from './RomIGDBMetadata';
import type { RomLaunchboxMetadata } from './RomLaunchboxMetadata';
import type { RomMetadataSchema } from './RomMetadataSchema';
import type { RomMobyMetadata } from './RomMobyMetadata';
import type { RomPouetMetadata } from './RomPouetMetadata';
import type { RomRAMetadata } from './RomRAMetadata';
import type { RomSSMetadata } from './RomSSMetadata';
import type { RomSteamMetadata } from './RomSteamMetadata';
import type { RomUserSchema } from './RomUserSchema';
import type { SaveSchema } from './SaveSchema';
import type { SaveTargetLayout } from './SaveTargetLayout';
import type { ScreenshotSchema } from './ScreenshotSchema';
import type { SiblingRomSchema } from './SiblingRomSchema';
import type { StateSchema } from './StateSchema';
import type { UserCollectionSchema } from './UserCollectionSchema';
import type { UserNoteSchema } from './UserNoteSchema';
import type { UserSaveSchema } from './UserSaveSchema';
import type { UserScreenshotSchema } from './UserScreenshotSchema';
import type { UserStateSchema } from './UserStateSchema';
export type DetailedRomSchema = {
    id: number;
    igdb_id: (number | null);
    /**
     * The SteamGridDB game ID, used to find artwork.
     */
    sgdb_id: (number | null);
    moby_id: (number | null);
    ss_id: (number | null);
    ra_id: (number | null);
    launchbox_id: (number | null);
    hasheous_id: (number | null);
    tgdb_id: (number | null);
    flashpoint_id: (string | null);
    hltb_id: (number | null);
    /**
     * The Demozoo production ID, for demoscene releases.
     */
    demozoo_id: (number | null);
    /**
     * The Pouët production ID, for demoscene releases.
     */
    pouet_id: (number | null);
    /**
     * The CSDb release ID, for Commodore 64 releases.
     */
    csdb_id: (number | null);
    steam_id: (number | null);
    /**
     * A random ID generated for the ES-DE `gamelist.xml` entry when it was read.
     */
    gamelist_id: (string | null);
    /**
     * The SHA-1 hash of the matched Libretro artwork's file name.
     */
    libretro_id: (string | null);
    platform_id: number;
    platform_slug: string;
    /**
     * The name of the platform's folder in the library.
     */
    platform_fs_slug: string;
    platform_custom_name: (string | null);
    /**
     * The custom name when set, otherwise the platform's own name.
     */
    platform_display_name: string;
    /**
     * The file or folder name, extension included.
     */
    fs_name: string;
    /**
     * The name without its extension or any tags in parentheses or brackets. `Example Game (USA) (Rev 1).z64` becomes `Example Game`.
     */
    fs_name_no_tags: string;
    /**
     * The name without its extension. Tags are kept, so the same file becomes `Example Game (USA) (Rev 1)`.
     */
    fs_name_no_ext: string;
    /**
     * The file extension without the dot, such as `z64`. Empty for a folder.
     */
    fs_extension: string;
    /**
     * The folder holding the rom, relative to the library root.
     */
    fs_path: string;
    /**
     * The total size of all the rom's files, in bytes.
     */
    fs_size_bytes: number;
    /**
     * The display name, from the matched metadata or the file name.
     */
    name: (string | null);
    /**
     * The key used to sort by name: the name in lowercase, without a leading article. `The Old Game` becomes `old game`.
     */
    name_sort_key: (string | null);
    slug: (string | null);
    summary: (string | null);
    /**
     * Other titles the game is known by, excluding the display name. If the user has set titles by hand, only those are used. Otherwise they come from IGDB, MobyGames and ScreenScraper.
     */
    alternative_names: Array<string>;
    youtube_video_id: (string | null);
    /**
     * The metadata merged from every matched provider, used for filtering and sorting.
     */
    metadatum: RomMetadataSchema;
    /**
     * The raw IGDB metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    igdb_metadata: (RomIGDBMetadata | null);
    /**
     * The raw MobyGames metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    moby_metadata: (RomMobyMetadata | null);
    /**
     * The raw ScreenScraper metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    ss_metadata: (RomSSMetadata | null);
    /**
     * The raw LaunchBox metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    launchbox_metadata: (RomLaunchboxMetadata | null);
    /**
     * The raw Hasheous metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    hasheous_metadata: (RomHasheousMetadata | null);
    /**
     * The raw Flashpoint Project metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    flashpoint_metadata: (RomFlashpointMetadata | null);
    /**
     * The raw HowLongToBeat metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    hltb_metadata: (RomHLTBMetadata | null);
    /**
     * The raw Demozoo metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    demozoo_metadata: (RomDemozooMetadata | null);
    /**
     * The raw Pouët metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    pouet_metadata: (RomPouetMetadata | null);
    /**
     * The raw CSDb metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    csdb_metadata: (RomCsdbMetadata | null);
    /**
     * The raw Steam metadata. An empty object when there is no match, and null when `with_provider_metadata` is false.
     */
    steam_metadata: (RomSteamMetadata | null);
    /**
     * The raw ES-DE `gamelist.xml` metadata. An empty object when there is no entry, and null when `with_provider_metadata` is false.
     */
    gamelist_metadata: (RomGamelistMetadata | null);
    /**
     * The metadata the user entered by hand. It takes precedence over provider metadata in `metadatum`.
     */
    manual_metadata: (ManualMetadata | null);
    /**
     * The path to the small cover, with a cache-busting timestamp. Empty when there is no cover.
     */
    path_cover_small: (string | null);
    /**
     * The path to the large cover, with a cache-busting timestamp. Empty when there is no cover.
     */
    path_cover_large: (string | null);
    /**
     * The remote URL the cover was fetched from.
     */
    url_cover: (string | null);
    has_manual: boolean;
    has_soundtrack: boolean;
    path_manual: (string | null);
    /**
     * The remote URL the manual was fetched from.
     */
    url_manual: (string | null);
    /**
     * The path to a video, taken from the ScreenScraper, ES-DE or LaunchBox metadata, in that order of preference.
     */
    path_video: (string | null);
    /**
     * True while a scan is looking up metadata for the rom.
     */
    is_identifying?: boolean;
    /**
     * True when no provider has matched the rom.
     */
    is_unidentified: boolean;
    /**
     * True when at least one provider has matched the rom.
     */
    is_identified: boolean;
    /**
     * The revision read from the file name tags.
     */
    revision: (string | null);
    /**
     * The version read from the file name tags.
     */
    version: (string | null);
    /**
     * The regions read from the file name tags, such as `Europe`.
     */
    regions: Array<string>;
    /**
     * The languages read from the file name tags.
     */
    languages: Array<string>;
    /**
     * The other tags read from the file name.
     */
    tags: Array<string>;
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    /**
     * The hash RetroAchievements uses to identify the rom. Empty if it has not been computed.
     */
    ra_hash: (string | null);
    /**
     * The platform's own ID for the game, read from the rom file and normalized, such as `SLUS-20152`.
     */
    title_id: (string | null);
    /**
     * The on-disk name an emulator gives the game's saves: a file stem, a folder or a nested path.
     */
    save_target: (string | null);
    /**
     * How to read `save_target`: as a single folder, a single file, a folder prefix, a file prefix or a nested path.
     */
    save_target_layout: (SaveTargetLayout | null);
    /**
     * True for a single file at the top level.
     */
    has_simple_single_file: boolean;
    /**
     * True for a folder holding exactly one top-level file.
     */
    has_nested_single_file: boolean;
    /**
     * True when more than one file or folder sits at the top level.
     */
    has_multiple_files: boolean;
    /**
     * True for an RPG Maker 2000 or 2003 game: a folder containing an `rpg_rt.ldb` database.
     */
    is_easyrpg_game: boolean;
    /**
     * True when the ROM is a `.jsdos` bundle, or a folder with one at its top level.
     */
    has_jsdos_bundle: boolean;
    /**
     * The path of the file or folder relative to the library root: `fs_path` joined with `fs_name`.
     */
    full_path: string;
    created_at: string;
    updated_at: string;
    /**
     * True when the file or folder is gone from disk. The record stays until the missing-roms cleanup runs.
     */
    missing_from_fs: boolean;
    /**
     * True for a physical copy with no file.
     */
    is_physical: boolean;
    /**
     * Whether a readable file backs the rom. False for physical games and for roms whose file is missing.
     */
    has_file_on_disk: boolean;
    /**
     * The barcode of a physical game, used to look up its title when no name is given.
     */
    upc: (string | null);
    /**
     * Whether the current user can see a note on the rom.
     */
    has_notes: boolean;
    /**
     * The current user's data for the rom, such as status and rating.
     */
    rom_user: RomUserSchema;
    /**
     * The paths of the screenshots a scan downloaded from the metadata providers.
     */
    merged_screenshots: Array<string>;
    /**
     * The RetroAchievements metadata with its achievements sorted for display.
     */
    merged_ra_metadata: (RomRAMetadata | null);
    /**
     * The rom's files. Lists include them only when `with_files` is true.
     */
    files: Array<RomFileSchema>;
    /**
     * The other versions of this game on the platform, excluding any the user cannot see.
     */
    sibling_roms: Array<SiblingRomSchema>;
    /**
     * The caller's own saves for the rom.
     */
    user_saves: Array<SaveSchema>;
    /**
     * The caller's own states for the rom.
     */
    user_states: Array<StateSchema>;
    /**
     * The caller's own saves and other users' public saves, each with its owner's name and avatar.
     */
    all_user_saves: Array<UserSaveSchema>;
    /**
     * The caller's own states and other users' public states, each with its owner's name and avatar.
     */
    all_user_states: Array<UserStateSchema>;
    /**
     * The caller's sync channels for the rom, followed by other users' public channels.
     */
    user_channels: Array<ChannelSchema>;
    /**
     * The ID of the file that a new channel for this rom is attached to.
     */
    channel_file_id: (number | null);
    /**
     * The IDs of the saves that belong to a channel. Any save not listed here was uploaded to a slot the legacy way.
     */
    snapshot_save_ids: Array<number>;
    /**
     * The caller's own screenshots for the rom.
     */
    user_screenshots: Array<ScreenshotSchema>;
    /**
     * The gallery screenshots the caller can see: their own and other users' public ones. Thumbnails captured with saves and states are not included.
     */
    all_user_screenshots: Array<UserScreenshotSchema>;
    /**
     * The collections containing the rom that the caller can see, both their own and other users' public ones, including smart collections.
     */
    user_collections: Array<UserCollectionSchema>;
    /**
     * The notes the caller can see, most recently updated first.
     */
    all_user_notes: Array<UserNoteSchema>;
    /**
     * The formats the caller can request with `?format=` when downloading the rom's file. Only set for roms with a single file.
     */
    download_formats: Array<string>;
};

