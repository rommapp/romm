/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FirmwareSchema } from './FirmwareSchema';
/**
 * A platform: a console, handheld or other system with roms in the library.
 */
export type PlatformSchema = {
    /**
     * The internal ID of the platform.
     */
    id: number;
    /**
     * The canonical slug, such as `snes`.
     */
    slug: string;
    /**
     * The name of the platform's folder in the library.
     */
    fs_slug: string;
    /**
     * The number of roms on the platform that the caller can see.
     */
    rom_count: number;
    /**
     * The name of the platform.
     */
    name: string;
    /**
     * The IGDB slug of the platform.
     */
    igdb_slug: (string | null);
    /**
     * The MobyGames slug of the platform.
     */
    moby_slug: (string | null);
    /**
     * The HowLongToBeat slug of the platform.
     */
    hltb_slug: (string | null);
    /**
     * The Libretro slug of the platform.
     */
    libretro_slug: (string | null);
    /**
     * The name the user gave the platform in place of its own.
     */
    custom_name?: (string | null);
    /**
     * The description of the platform.
     */
    description?: (string | null);
    /**
     * The IGDB ID of the platform.
     */
    igdb_id?: (number | null);
    /**
     * The SteamGridDB ID of the platform, used to find artwork.
     */
    sgdb_id?: (number | null);
    /**
     * The MobyGames ID of the platform.
     */
    moby_id?: (number | null);
    /**
     * The LaunchBox ID of the platform.
     */
    launchbox_id?: (number | null);
    /**
     * The ScreenScraper ID of the platform.
     */
    ss_id?: (number | null);
    /**
     * The RetroAchievements ID of the platform.
     */
    ra_id?: (number | null);
    /**
     * The Hasheous ID of the platform.
     */
    hasheous_id?: (number | null);
    /**
     * The TheGamesDB ID of the platform.
     */
    tgdb_id?: (number | null);
    /**
     * The Flashpoint Project ID of the platform.
     */
    flashpoint_id?: (number | null);
    /**
     * The category of the platform.
     */
    category?: (string | null);
    /**
     * The hardware generation of the platform.
     */
    generation?: (number | null);
    /**
     * The year the platform was first released.
     */
    first_release_year?: (number | null);
    /**
     * The name of the platform family.
     */
    family_name?: (string | null);
    /**
     * The slug of the platform family.
     */
    family_slug?: (string | null);
    /**
     * The URL of a web page about the platform.
     */
    url?: (string | null);
    /**
     * The URL of the platform's logo.
     */
    url_logo?: (string | null);
    /**
     * The platform's firmware files, such as BIOS images.
     */
    firmware?: Array<FirmwareSchema>;
    /**
     * When the platform was added to the library.
     */
    created_at: string;
    /**
     * When the platform's record last changed.
     */
    updated_at: string;
    /**
     * The total size of the platform's roms on disk, in bytes.
     */
    fs_size_bytes: number;
    /**
     * True when no provider has matched the platform.
     */
    is_unidentified: boolean;
    /**
     * True when at least one provider has matched the platform.
     */
    is_identified: boolean;
    /**
     * True when the platform's folder is no longer in the library.
     */
    missing_from_fs: boolean;
    /**
     * The custom name when set, otherwise the platform's name.
     */
    readonly display_name: string;
    /**
     * The short name of the platform.
     */
    readonly abbreviation: string;
    /**
     * Other names the platform is known by.
     */
    readonly alternative_names: Array<string>;
    /**
     * The number of firmware files, usable or not.
     */
    readonly firmware_count: number;
};

