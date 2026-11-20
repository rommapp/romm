/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
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
import type { SaveTargetLayout } from './SaveTargetLayout';
import type { SiblingRomSchema } from './SiblingRomSchema';
export type SimpleRomSchema = {
    /**
     * The internal ID of the rom.
     */
    id: number;
    /**
     * The IGDB game ID. Null when IGDB has no match.
     */
    igdb_id: (number | null);
    /**
     * The SteamGridDB game ID, used to find artwork.
     */
    sgdb_id: (number | null);
    /**
     * The MobyGames game ID. Null when there is no match.
     */
    moby_id: (number | null);
    /**
     * The ScreenScraper game ID. Null when there is no match.
     */
    ss_id: (number | null);
    /**
     * The RetroAchievements game ID. Null when there is no match.
     */
    ra_id: (number | null);
    /**
     * The LaunchBox database ID. Null when there is no match.
     */
    launchbox_id: (number | null);
    /**
     * The Hasheous game ID. Null when there is no match.
     */
    hasheous_id: (number | null);
    /**
     * The TheGamesDB game ID. Null when there is no match.
     */
    tgdb_id: (number | null);
    /**
     * The Flashpoint Project entry ID. Null when there is no match.
     */
    flashpoint_id: (string | null);
    /**
     * The HowLongToBeat game ID. Null when there is no match.
     */
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
    /**
     * The Steam app ID. Null when there is no match.
     */
    steam_id: (number | null);
    /**
     * A random ID generated for the ES-DE `gamelist.xml` entry when it was read.
     */
    gamelist_id: (string | null);
    /**
     * The SHA-1 hash of the matched Libretro artwork's file name.
     */
    libretro_id: (string | null);
    /**
     * The internal ID of the platform.
     */
    platform_id: number;
    /**
     * The platform's canonical slug, such as `snes`.
     */
    platform_slug: string;
    /**
     * The name of the platform's folder in the library.
     */
    platform_fs_slug: string;
    /**
     * The name the user gave the platform. Null when they did not rename it.
     */
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
     * The key the gallery sorts by name: lowercase, without a leading article. `The Old Game` becomes `old game`.
     */
    name_sort_key: (string | null);
    /**
     * The URL-friendly form of the name.
     */
    slug: (string | null);
    /**
     * The description of the game.
     */
    summary: (string | null);
    /**
     * Other titles the game is known by, without the display name. The hand-set titles when there are any, otherwise those from IGDB, MobyGames and ScreenScraper.
     */
    alternative_names: Array<string>;
    /**
     * The ID of a YouTube video for the game, when a provider supplies one.
     */
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
    /**
     * Whether a manual is stored for the rom.
     */
    has_manual: boolean;
    /**
     * Whether the rom has soundtrack files.
     */
    has_soundtrack: boolean;
    /**
     * The path to the stored manual.
     */
    path_manual: (string | null);
    /**
     * The remote URL the manual was fetched from.
     */
    url_manual: (string | null);
    /**
     * The path to a video, from the first of ScreenScraper, ES-DE and LaunchBox metadata that has one.
     */
    path_video: (string | null);
    /**
     * True only while a scan is matching the rom.
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
    /**
     * The CRC32 hash of the rom's content. Empty when it was not computed.
     */
    crc_hash: (string | null);
    /**
     * The MD5 hash of the rom's content. Empty when it was not computed.
     */
    md5_hash: (string | null);
    /**
     * The SHA-1 hash of the rom's content. Empty when it was not computed.
     */
    sha1_hash: (string | null);
    /**
     * The hash RetroAchievements matches the rom on. Empty when it was not computed.
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
     * How `save_target` applies: as one folder, one file, a folder prefix, a file prefix or a nested path.
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
     * True for a folder with an `rpg_rt.ldb` database, an RPG Maker 2000 or 2003 game.
     */
    is_easyrpg_game: boolean;
    /**
     * The `fs_path` and `fs_name` joined, relative to the library root.
     */
    full_path: string;
    /**
     * When the rom was added to the library.
     */
    created_at: string;
    /**
     * When the rom's record last changed.
     */
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
     * The barcode of a physical game. It looks up the title when no name is given.
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
     * The paths of the stored screenshots.
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
     * The other versions of this game on the platform, minus any the user cannot see.
     */
    sibling_roms: Array<SiblingRomSchema>;
    /**
     * The "where you left off" image: the latest save's screenshot, else the title screen, else the first gameplay screenshot. Set only when `last_played` is true.
     */
    screenshot_path?: (string | null);
};

